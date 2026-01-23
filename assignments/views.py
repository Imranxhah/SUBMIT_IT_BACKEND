import datetime
import os
import markdown
import time
import uuid
import threading
import tempfile
import shutil
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponse, FileResponse
from weasyprint import HTML
from groq import Groq
from .utils import convert_to_pdf, extract_with_diagram_text
from .models import AssignmentSubmission, AdReward

# --- CONFIGURATION ---
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

VALID_GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "mixtral-8x7b-32768",
    "llama-3.1-8b-instant",
    "gemma2-9b-it"
]

def get_submission_status(user):
    """
    Helper to calculate submission stats for a user.
    """
    now = timezone.now()
    last_24h = now - datetime.timedelta(hours=24)
    
    active_submissions = AssignmentSubmission.objects.filter(
        user=user, 
        created_at__gte=last_24h
    ).order_by('created_at')
    
    submission_count = active_submissions.count()
    
    reward_count = AdReward.objects.filter(
        user=user,
        created_at__gte=last_24h
    ).count()
    
    base_limit = getattr(settings, 'DAILY_SUBMISSION_LIMIT', 3)
    effective_limit = base_limit + reward_count
    remaining = max(0, effective_limit - submission_count)
    
    next_reset_time = None
    if submission_count >= effective_limit:
        oldest_submission = active_submissions.first()
        if oldest_submission:
            next_reset_time = oldest_submission.created_at + datetime.timedelta(hours=24)
    elif submission_count > 0:
        oldest_submission = active_submissions.first()
        if oldest_submission:
             next_reset_time = oldest_submission.created_at + datetime.timedelta(hours=24)

    return {
        "limit": effective_limit,
        "used": submission_count,
        "remaining": remaining,
        "next_reset_time": next_reset_time
    }

class AssignmentStatusView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        return Response(get_submission_status(request.user))

class RewardView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, *args, **kwargs):
        AdReward.objects.create(user=request.user)
        return Response({
            "message": "Reward claimed.",
            "status": get_submission_status(request.user)
        }, status=200)

# --- BACKGROUND WORKER ---

def process_assignment_task(task_id, temp_input_path, original_filename, form_data, user_data):
    """
    Background thread logic.
    Updates cache with progress.
    Saves final PDF to a temp file path stored in cache.
    """
    try:
        extracted_text = ""
        ext = os.path.splitext(original_filename)[1].lower()

        if ext == '.txt':
            # DIRECT TEXT READ (No PDF Conversion)
            cache.set(task_id, {"status": "processing", "progress": 20, "message": "Reading text file..."}, timeout=300)
            try:
                with open(temp_input_path, 'r', encoding='utf-8') as f:
                    extracted_text = f.read()
            except UnicodeDecodeError:
                # Fallback decoding
                with open(temp_input_path, 'r', encoding='latin-1') as f:
                    extracted_text = f.read()
        else:
            # 1. Conversion
            cache.set(task_id, {"status": "processing", "progress": 10, "message": "Converting file format..."}, timeout=300)
            
            # Create a temp file for the unified PDF
            fd, temp_unified_pdf = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)
            
            convert_to_pdf(temp_input_path, temp_unified_pdf)
            
            # 2. Extraction
            cache.set(task_id, {"status": "processing", "progress": 30, "message": "Extracting text and diagrams..."}, timeout=300)
            extracted_text = extract_with_diagram_text(temp_unified_pdf)
            
            # Clean intermediate unified PDF
            if os.path.exists(temp_unified_pdf):
                try:
                    os.remove(temp_unified_pdf)
                except Exception as e:
                    print(f"Warning: Could not delete temp PDF {temp_unified_pdf}: {e}")

        # --- VALIDATION ---
        cleaned_text = extracted_text.strip()
        if not cleaned_text:
            raise ValueError("The extracted content is empty. Please upload a file with readable text.")
        
        if len(cleaned_text) > 10000:
            raise ValueError(f"File content is too large ({len(cleaned_text)} characters). Limit is 10,000 characters.")
            
        extracted_text = cleaned_text

        # 3. AI Generation
        cache.set(task_id, {"status": "processing", "progress": 60, "message": "Analyzing with AI..."}, timeout=300)
        
        assignment_number = form_data.get('assignment_number')
        subject_name = form_data.get('subject_name')
        teacher_name = form_data.get('teacher_name')
        
        system_instruction = (
            "You are a helpful academic expert. "
            "1. Answer the user's question(s) clearly and in detail. "
            "2. If comparing items, provide a Markdown table. "
            "3. Use proper Markdown formatting (headings, bold, lists). "
            "4. Provide the reponse in Question/Answer format."
        )
        user_prompt = f"This is a {subject_name} assignment. Answer the question(s) in this assignment with detail:\n\n{extracted_text}"
        
        ai_response_text = None
        used_model = None
        
        for model_id in VALID_GROQ_MODELS:
            try:
                completion = client.chat.completions.create(
                    model=model_id,
                    messages=[
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.3,
                )
                ai_response_text = completion.choices[0].message.content
                used_model = model_id
                break
            except Exception as e:
                print(f"Error on {model_id}: {e}")
                continue
        
        if not ai_response_text:
            raise Exception("AI Service unavailable.")

        # 4. PDF Generation
        cache.set(task_id, {"status": "processing", "progress": 85, "message": "Generating final PDF..."}, timeout=300)
        
        current_date = datetime.date.today().strftime("%B %d, %Y")
        base_dir_formatted = str(settings.BASE_DIR).replace('\\', '/')
        ai_html_content = markdown.markdown(ai_response_text, extensions=['tables', 'fenced_code'])

        # HTML Template (Shortened for brevity, logic identical to original)
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                @font-face {{ font-family: 'CMU Serif'; src: url('file:///{base_dir_formatted}/static/fonts/cmunrm.ttf') format('truetype'); }}
                @font-face {{ font-family: 'CMU Serif'; src: url('file:///{base_dir_formatted}/static/fonts/cmunbx.ttf') format('truetype'); font-weight: bold; }}
                @font-face {{ font-family: 'CMU Typewriter'; src: url('file:///{base_dir_formatted}/static/fonts/cmuntt.ttf') format('truetype'); }}
                @page {{ size: A4; margin: 1in; }}
                body {{ font-family: 'CMU Serif', serif; margin: 0; }}
                .title-page {{ height: 100vh; page-break-after: always; text-align: center; display: flex; flex-direction: column; justify-content: center; }}
                .uni-name {{ font-size: 18pt; margin-bottom: 1cm; font-variant: small-caps; }}
                .course-name {{ font-size: 28pt; margin-bottom: 1.5cm; font-variant: small-caps; }}
                .assignment-title {{ font-size: 24pt; font-weight: bold; text-transform: uppercase; padding: 10px 0; }}
                .thick-rule {{ width: 100%; height: 2px; background-color: black; margin: 0.4cm 0; }}
                .section {{ margin-bottom: 2cm; }}
                .label {{ font-size: 16pt; font-weight: bold; margin-bottom: 0.5cm; }}
                .name, .instructor {{ font-size: 24pt; margin-bottom: 0.2cm; }}
                .reg-no {{ font-size: 18pt; }}
                .content-page {{ font-size: 14pt; line-height: 1.6; text-align: left; }}
                .content-page h1 {{ font-size: 18pt; border-bottom: 2px solid #000; padding-bottom: 5px; margin-top: 25px; }}
                .content-page table {{ width: 100%; border-collapse: collapse; margin: 25px 0; font-size: 13pt; }}
                .content-page th {{ background-color: #000; color: #fff; padding: 12px; }}
                .content-page td {{ padding: 12px; border: 1px solid #ddd; }}
                .footer-note {{ margin-top: 50px; font-size: 9pt; color: #7f8c8d; text-align: center; border-top: 1px solid #eee; padding-top: 10px; }}
                pre, code {{ font-family: 'CMU Typewriter', monospace; background: #f4f4f4; }}
            </style>
        </head>
        <body>
            <div class="title-page">
                <div class="uni-name">{user_data['university_name']}<br>{user_data['department']}</div>
                <div class="course-name">{subject_name}</div>
                <div class="title-block">
                    <div class="thick-rule"></div>
                    <div class="assignment-title">ASSIGNMENT NUMBER: {assignment_number}</div>
                    <div class="thick-rule"></div>
                </div>
                <div class="section">
                    <div class="label">Submitted By:</div>
                    <div class="name">{user_data['first_name']} {user_data['last_name']}</div>
                    <div class="reg-no">Reg. No: {user_data['registration_number']}</div>
                </div>
                <div class="section">
                    <div class="label">Submitted To:</div>
                    <div class="instructor">{teacher_name}</div>
                </div>
                <div>Submission Date: {current_date}</div>
            </div>
            <div class="content-page">
                {ai_html_content}
                <div class="footer-note">Generated by AI ({used_model}) on {current_date}</div>
            </div>
        </body>
        </html>
        """
        
        # Save Final PDF to a new temp file
        fd_final, final_pdf_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd_final)
        
        HTML(string=html_content).write_pdf(final_pdf_path)
        
        # Construct filename
        raw_filename = f"{subject_name} Assignment {assignment_number} {user_data['first_name']} {user_data['last_name']}.pdf"
        clean_filename = raw_filename.title().replace(" ", "_")

        # 5. Success
        cache.set(task_id, {
            "status": "completed", 
            "progress": 100, 
            "result_path": final_pdf_path,
            "filename": clean_filename
        }, timeout=600) # Keep result for 10 mins

    except Exception as e:
        cache.set(task_id, {"status": "failed", "error": str(e)}, timeout=300)
    
    finally:
        # Cleanup INPUT file
        if os.path.exists(temp_input_path):
            try:
                os.remove(temp_input_path)
            except:
                pass

# --- API VIEWS ---

class StartAssignmentTaskView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        user = request.user
        
        # Check Limits
        stats = get_submission_status(user)
        if stats['used'] >= stats['limit']:
            return Response({"error": "Daily limit reached.", "reset_in": stats['next_reset_time']}, status=403)

        # Validate Data
        assignment_number = request.data.get('assignment_number')
        subject_name = request.data.get('subject_name')
        teacher_name = request.data.get('teacher_name')
        uploaded_file = request.FILES.get('assignment_file')

        if not all([assignment_number, subject_name, teacher_name, uploaded_file]):
            return Response({"error": "All fields required."}, status=400)

        # Save to Temp
        ext = os.path.splitext(uploaded_file.name)[1]
        fd, temp_input_path = tempfile.mkstemp(suffix=ext)
        os.close(fd)
        
        with open(temp_input_path, 'wb+') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)

        # Prepare Data for Thread
        user_data = {
            'first_name': user.first_name,
            'last_name': user.last_name,
            'registration_number': user.registration_number,
            'university_name': user.university_name or "University Name Not Set",
            'department': user.department or "Department Not Set"
        }
        
        form_data = {
            'assignment_number': assignment_number,
            'subject_name': subject_name,
            'teacher_name': teacher_name
        }

        # Start Task
        task_id = str(uuid.uuid4())
        thread = threading.Thread(
            target=process_assignment_task,
            args=(task_id, temp_input_path, uploaded_file.name, form_data, user_data)
        )
        thread.start()

        # Record Submission (Deduct quota immediately)
        AssignmentSubmission.objects.create(user=user)

        return Response({"task_id": task_id, "status": "processing", "progress": 0}, status=202)

class GetAssignmentProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        status_data = cache.get(task_id)
        if not status_data:
            return Response({"error": "Task not found or expired."}, status=404)
        
        return Response(status_data)

class DownloadAssignmentResultView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        status_data = cache.get(task_id)
        if not status_data or status_data.get('status') != 'completed':
            return Response({"error": "Result not ready or expired."}, status=404)
        
        result_path = status_data.get('result_path')
        filename = status_data.get('filename', 'assignment.pdf')

        if not os.path.exists(result_path):
            return Response({"error": "File already deleted."}, status=410)

        # Serve File and Delete
        try:
            # We open it, wrap in FileResponse, and ensure deletion happens AFTER response is served?
            # Standard FileResponse doesn't auto-delete.
            # We can read into memory if small, or use a cleanup approach.
            # Given requirement "Not store data", reading into memory (if <10MB) is safer for deletion.
            
            with open(result_path, 'rb') as f:
                file_content = f.read()
            
            # Now delete immediately
            os.remove(result_path)
            cache.delete(task_id) # Cleanup cache too

            response = HttpResponse(file_content, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        except Exception as e:
            return Response({"error": f"Download failed: {str(e)}"}, status=500)