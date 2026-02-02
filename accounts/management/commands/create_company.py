from django.core.management.base import BaseCommand
from django.db import IntegrityError
from accounts.models import User, Company
import getpass

class Command(BaseCommand):
    help = 'Creates a new Company and an HR Admin user via terminal'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('\n--- CREATE NEW COMPANY & HR ADMIN ---\n'))

        # 1. Get Company Details
        while True:
            company_name = input("Enter Company Name: ").strip()
            if company_name:
                break
            self.stdout.write(self.style.ERROR("Company name cannot be empty."))

        # 2. Get HR Details
        while True:
            username = input("Enter HR Username: ").strip()
            if username:
                break
            self.stdout.write(self.style.ERROR("Username cannot be empty."))

        while True:
            email = input("Enter HR Email: ").strip()
            if email:
                break
            self.stdout.write(self.style.ERROR("Email cannot be empty."))
        
        # Secure password input (hidden typing)
        while True:
            password = getpass.getpass("Enter HR Password: ")
            password_confirm = getpass.getpass("Confirm Password: ")

            if password == password_confirm and password:
                break
            else:
                self.stdout.write(self.style.ERROR("Passwords do not match or are empty. Try again."))

        # 3. Execution Logic
        try:
            # Step A: Create or Get Company
            company, created = Company.objects.get_or_create(
                name=company_name,
                defaults={'hr_email': email}
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f"✔ Company '{company_name}' created."))
            else:
                self.stdout.write(self.style.WARNING(f"ℹ Using existing company '{company_name}'."))

            # Step B: Create User
            if User.objects.filter(username=username).exists():
                self.stdout.write(self.style.ERROR(f"✘ User '{username}' already exists."))
                return

            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )

            # Step C: Assign HR Attributes
            user.role = 'HR'
            user.company = company
            user.is_approved = True
            user.is_staff = True
            user.save()

            self.stdout.write(self.style.SUCCESS(f"\n✔ SUCCESS: HR Admin '{username}' created for '{company_name}'!"))
            self.stdout.write(f"You can now login at: http://127.0.0.1:8000/login/\n")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))
