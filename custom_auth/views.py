from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages

# Login
def loginView(request):
    if request.method == 'POST':
        username = request.POST.get('username') 
        password = request.POST.get('password') 

        if not username or not password:
            messages.error(request, "Datas could not be empty!")
            return redirect('login')

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            messages.error(request, "User does not exist!")
            return redirect('login')
        user = authenticate(request, username=user.username, password=password)
        if user is not None and user.is_active:
            login(request, user)
            next_url = request.GET.get('next', 'index')
            return redirect(next_url)

        messages.error(request, "Username or password is incorrect!")
        return redirect('login')

    return render(request, 'custom_auth/login.html')


# Logout
def logoutView(request):
    logout(request)
    return redirect('index')

# Register
def registerView(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')  
        password = request.POST.get('password')  
        confirm_password = request.POST.get('confirm_password')  
        if not email or not password or not username:
            messages.error(request, "Datas could not be empty")
            return redirect('register')

        if password != confirm_password:
            messages.error(request, "Passwords do not match")
            return redirect('register')

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists")
            return redirect('register')
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
            return redirect('register')
        
        user = User.objects.create_user(username=username, email=email, password=password)
        user.save()

        messages.success(request, "Account created successfully")
        return redirect('login')  

    return render(request, 'custom_auth/register.html')

