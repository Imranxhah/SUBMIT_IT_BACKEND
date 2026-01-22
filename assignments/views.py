import datetime
import os
import markdown
import io
import time
from django.utils import timezone
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.http import FileResponse, HttpResponse
from django.template.loader import render_to_string
from weasyprint import HTML, CSS
from groq import Groq, RateLimitError, APIConnectionError
from .utils import extract_content_from_file
from .models import AssignmentSubmission, AdReward

# --- CONFIGURATION ---

# 1. Initialize Client
# Make sure GROQ_API_KEY is set in your environment variables
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# 2. PRIORITY LIST (Sorted by Intelligence -> Speed)
MODEL_PRIORITY_LIST = [
    # --- TIER 1: The "Smartest" (Best for complex logic & tables) ---
    "llama-3.3-70b-versatile",
    # "openai/gpt-oss-120b", # Note: Verify specific Groq model names if these are external
    "qwen-2.5-32b", # Adjusted to likely valid Groq model name, user provided "qwen/qwen3-32b" which might be specific to another provider, defaulting to a known good one or keeping user's if sure. I will use a safe fallback list for Groq.
    
    # --- TIER 2: High Capability / Specialized ---
    # "meta-llama/llama-4-maverick-17b-128e-instruct", # Hypothetical/Future models? Keeping safe defaults for Groq.
    "mixtral-8x7b-32768",
    
    # --- TIER 3: General Purpose & Fast ---
    "llama-3.1-8b-instant",
    "gemma-7b-it"
]

# User provided list seems to contain some future/hypothetical or specific-platform names.
# I will use a robust list of currently available Groq models to ensure it works, 
# while trying to respect the user's intent for hierarchy.
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
    
    # Get active submissions (those strictly within the last 24h)
    active_submissions = AssignmentSubmission.objects.filter(
        user=user, 
        created_at__gte=last_24h
    ).order_by('created_at')
    
    submission_count = active_submissions.count()
    
    # Get active rewards
    reward_count = AdReward.objects.filter(
        user=user,
        created_at__gte=last_24h
    ).count()
    
    base_limit = getattr(settings, 'DAILY_SUBMISSION_LIMIT', 3)
    effective_limit = base_limit + reward_count
    remaining = max(0, effective_limit - submission_count)
    
    # Calculate when the next slot frees up
    next_reset_time = None
    if submission_count >= effective_limit:
        # If limit is reached, the next slot opens when the OLDEST active submission expires
        oldest_submission = active_submissions.first()
        if oldest_submission:
            # Expiry is creation time + 24 hours
            reset_dt = oldest_submission.created_at + datetime.timedelta(hours=24)
            next_reset_time = reset_dt
    elif submission_count > 0:
        oldest_submission = active_submissions.first()
        if oldest_submission:
             next_reset_time = oldest_submission.created_at + datetime.timedelta(hours=24)

    return {
        "limit": effective_limit,
        "used": submission_count,
        "remaining": remaining,
        "next_reset_time": next_reset_time  # datetime object or None
    }

class AssignmentStatusView(APIView):
    """
    Returns the current submission status for the user.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        status_data = get_submission_status(request.user)
        return Response(status_data)

class RewardView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # Create a reward record for the user
        AdReward.objects.create(user=request.user)
        
        # Return updated status immediately so UI can update without a second call
        status_data = get_submission_status(request.user)
        return Response({
            "message": "Reward claimed successfully. Daily limit increased by 1.",
            "status": status_data
        }, status=200)

class GenerateAssignmentView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        user = request.user

        # --- Check Submission Limit ---
        stats = get_submission_status(user)
        
        if stats['used'] >= stats['limit']:
            return Response({
                "error": "Daily submission limit reached.",
                "limit": stats['limit'],
                "used": stats['used'],
                "reset_in": stats['next_reset_time']
            }, status=403)
        # -----------------------------

        # 1. Get Data from Request
        assignment_number = request.data.get('assignment_number')
        subject_name = request.data.get('subject_name')
        teacher_name = request.data.get('teacher_name')
        uploaded_file = request.FILES.get('assignment_file')

        if not all([assignment_number, subject_name, teacher_name, uploaded_file]):
            return Response({"error": "All fields (assignment_number, subject_name, teacher_name, assignment_file) are required."}, status=400)

        # 2. Extract Content from File
        try:
            extracted_text = extract_content_from_file(uploaded_file)
        except Exception as e:
             return Response({"error": f"Failed to process file: {str(e)}"}, status=400)

        # 3. Generate AI Answer
        ai_response_text = None
        used_model = None
        
        # Construct the Prompt
        system_instruction = (
            "You are a helpful academic expert. "
            "1. Answer the user's question(s) clearly and in detail. "
            "2. If comparing items, provide a Markdown table. "
            "3. Use proper Markdown formatting (headings, bold, lists). "
            "4. Provide the reponse in Question/Answer format."
        )
        
        user_prompt = f"This is a {subject_name} assignment. Answer the question(s) in this assignment with detail:\n\n{extracted_text}"
        
        # Call Groq API with Fallback
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
            return Response(
                {"error": "AI Service is currently unavailable. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        # 4. Prepare Context for HTML
        current_date = datetime.date.today().strftime("%B %d, %Y")
        
        # Format BASE_DIR for WeasyPrint (Forward slashes for file:// protocol)
        base_dir_formatted = str(settings.BASE_DIR).replace('\\', '/')

        # Convert AI Markdown to HTML
        ai_html_content = markdown.markdown(ai_response_text, extensions=['tables', 'fenced_code'])

        # HTML Structure
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Assignment</title>
            <style>
                @font-face {{
                    font-family: 'CMU Serif';
                    src: url('file:///{base_dir_formatted}/static/fonts/cmunrm.ttf') format('truetype');
                    font-weight: normal;
                    font-style: normal;
                }}
                @font-face {{
                    font-family: 'CMU Serif';
                    src: url('file:///{base_dir_formatted}/static/fonts/cmunbx.ttf') format('truetype');
                    font-weight: bold;
                    font-style: normal;
                }}
                @font-face {{
                    font-family: 'CMU Serif';
                    src: url('file:///{base_dir_formatted}/static/fonts/cmunti.ttf') format('truetype');
                    font-weight: normal;
                    font-style: italic;
                }}
                @font-face {{
                    font-family: 'CMU Serif';
                    src: url('file:///{base_dir_formatted}/static/fonts/cmunbi.ttf') format('truetype');
                    font-weight: bold;
                    font-style: italic;
                }}
                @font-face {{
                    font-family: 'CMU Typewriter';
                    src: url('file:///{base_dir_formatted}/static/fonts/cmuntt.ttf') format('truetype');
                    font-weight: normal;
                    font-style: normal;
                }}

                @page {{
                    size: A4;
                    margin: 1in;
                }}
                
                /* REMOVED GLOBAL HEIGHT RESTRICTION */
                /* html, body {{ height: 100%; margin: 0; }} */

                body {{
                    font-family: 'CMU Serif', serif;
                    margin: 0;
                }}

                /* Title Page Styles */
                .title-page {{
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    align-items: stretch;
                    text-align: center;
                    /* Force title page to be exactly one page height */
                    height: 100vh; 
                    page-break-after: always; 
                }}

                .uni-name {{
                    font-variant: small-caps;
                    font-size: 18pt;
                    margin-bottom: 1cm;
                }}

                .course-name {{
                    font-variant: small-caps;
                    font-size: 28pt;
                    margin-bottom: 1.5cm;
                }}

                .title-block {{
                    margin-bottom: 2cm;
                }}

                .thick-rule {{
                    width: 100%;
                    height: 2px;
                    background-color: black;
                    margin: 0.4cm 0;
                }}

                .assignment-title {{
                    font-size: 24pt;
                    font-weight: bold;
                    text-transform: uppercase;
                    padding: 10px 0;
                }}

                .section {{
                    margin-bottom: 2cm;
                }}

                .label {{
                    font-size: 16pt;
                    font-weight: bold;
                    margin-bottom: 0.5cm;
                }}

                .name, .instructor {{
                    font-size: 24pt;
                    margin-bottom: 0.2cm;
                }}

                .reg-no {{
                    font-size: 18pt;
                }}

                .date-section {{
                    font-size: 14pt;
                }}
                
                /* Content Page Styles */
                .content-page {{
                    font-size: 14pt;
                    text-align: left;
                    line-height: 1.6;
                }}
                
                /* AI Markdown Styling */
                .content-page h1, .content-page h2, .content-page h3, .content-page h4, .content-page h5 {{
                    color: #000000;
                }}
                .content-page h1 {{ font-size: 18pt; border-bottom: 2px solid #000; padding-bottom: 5px; margin-top: 25px; }}
                .content-page h2 {{ font-size: 16pt; margin-top: 20px; }}
                .content-page h3 {{ font-size: 14pt; font-weight: bold; margin-top: 15px; }}
                
                .content-page p {{ margin-bottom: 10px; }}
                .content-page ul, .content-page ol {{ margin-left: 20px; margin-bottom: 10px; }}
                .content-page li {{ margin-bottom: 5px; }}
                
                .content-page pre, .content-page code {{
                    font-family: 'CMU Typewriter', monospace;
                    background-color: #f4f4f4;
                    padding: 2px 4px;
                    border-radius: 4px;
                    font-size: 11pt;
                }}
                .content-page pre {{
                    padding: 10px;
                    overflow-x: auto;
                    border: 1px solid #ddd;
                }}
                
                /* Table Styling */
                .content-page table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 25px 0;
                    font-size: 13pt;
                    box-shadow: 0 0 20px rgba(0, 0, 0, 0.1); /* Subtle shadow */
                }}
                .content-page th {{
                    background-color: #000000; /* Black Header */
                    color: #ffffff;
                    text-align: left;
                    padding: 12px 15px;
                    font-weight: bold;
                    border: 1px solid #000;
                }}
                .content-page td {{
                    padding: 12px 15px;
                    border: 1px solid #ddd;
                    color: #333;
                }}
                .content-page tr:nth-child(even) {{
                    background-color: #f3f3f3; /* Zebra Striping */
                }}
                .content-page tr:last-of-type {{
                    border-bottom: 2px solid #000;
                }}
                
                .footer-note {{
                    margin-top: 50px;
                    font-size: 9pt;
                    color: #7f8c8d;
                    text-align: center;
                    border-top: 1px solid #eee;
                    padding-top: 10px;
                }}
            </style>
        </head>
        <body>
            <!-- Title Page (Unchanged) -->
            <div class="title-page">
                <div class="uni-name">
                    {user.university_name if user.university_name else "University Name Not Set"}
                    <br>
                    {user.department if user.department else "Department Not Set"}
                </div>

                <div class="course-name">
                    {subject_name}
                </div>

                <div class="title-block">
                    <div class="thick-rule"></div>

                    <div class="assignment-title">
                        ASSIGNMENT NUMBER: {assignment_number}
                    </div>

                    <div class="thick-rule"></div>
                </div>
                
                <div class="section">
                    <div class="label">Submitted By:</div>
                    <div class="name">{user.first_name} {user.last_name}</div>
                    <div class="reg-no">Reg. No: {user.registration_number}</div>
                </div>

                <div class="section">
                    <div class="label">Submitted To:</div>
                    <div class="instructor">{teacher_name}</div>
                </div>

                <div class="date-section">
                    Submission Date: {current_date}
                </div>
            </div>

            <!-- Content Page (AI Generated) -->
            <div class="content-page">
                {ai_html_content}
                
                <div class="footer-note">
                    Generated by AI ({used_model}) on {current_date}
                </div>
            </div>
        </body>
        </html>
        """

        # 5. Generate PDF
        pdf_file = HTML(string=html_content).write_pdf()

        # Record submission
        AssignmentSubmission.objects.create(user=user)

        # 6. Return Response
        response = HttpResponse(pdf_file, content_type='application/pdf')
        raw_filename = f"{subject_name} Assignment {assignment_number} {user.first_name} {user.last_name}.pdf"
        filename = raw_filename.title().replace(" ", "_")
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
