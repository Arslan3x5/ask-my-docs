from django.http import HttpResponse


def home(request):
    return HttpResponse("AskMyDocs is running.")
