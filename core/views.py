from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .models import AppVersion
from .serializers import AppVersionSerializer

class AppVersionView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            latest_version = AppVersion.objects.latest()
            serializer = AppVersionSerializer(latest_version)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except AppVersion.DoesNotExist:
            return Response({"error": "No version info found"}, status=status.HTTP_404_NOT_FOUND)