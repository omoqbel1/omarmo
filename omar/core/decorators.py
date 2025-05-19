from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect

def approved_required(view_func):
    @login_required(login_url='login')  # Explicitly set login_url
    def wrapper(request, *args, **kwargs):
        # Check if user is authenticated
        if not request.user.is_authenticated:
            messages.error(request, 'Please log in to access this page.')
            return redirect('login')

        # Check for user profile and approval status
        try:
            if hasattr(request.user, 'userprofile') and request.user.userprofile.is_approved:
                return view_func(request, *args, **kwargs)
            else:
                messages.error(request, 'Your account is not approved yet.')
                return redirect('login')
        except AttributeError:
            # Handle cases where userprofile might not exist
            messages.error(request, 'User profile not found. Please contact support.')
            return redirect('login')

    return wrapper
