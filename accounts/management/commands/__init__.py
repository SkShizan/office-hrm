from django.core.management.base import BaseCommand
from accounts.models import User, Company
from django.utils.text import slugify
import getpass

class Command(BaseCommand):
    help = 'Creates a new Company and an HR Admin user via terminal'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('--- CREATE NEW COMPANY & HR ---'))

        # 1. Get Company Details
        company_name = input("Enter Company Name: ").strip()
        if not company_name:
            self.stdout.write(self.style.ERROR("Company name cannot be empty."))
            return

        # 2. Get HR Details
        username = input("Enter HR Username: ").strip()
        email = input("Enter HR Email: ").strip()
        
        # Secure password input
        password = getpass.getpass("Enter HR Password: ")
        password_confirm = getpass.getpass("Confirm Password: ")

        if password != password_confirm:
            self.stdout.write(self.style.ERROR("Passwords do not match."))
            return

        # 3. Create Logic
        try:
            # Create Company
            company, created = Company.objects.get_or_create(
                name=company_name,
                defaults={'hr_email': email}
            )
            
            if created:
                self.stdout.write(f"Company '{company_name}' created.")
            else:
                self.stdout.write(f"Using existing company '{company_name}'.")

            # Create User
            if User.objects.filter(username=username).exists():
                self.stdout.write(self.style.ERROR("Username already taken."))
                return

            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                role='HR',              # Force Role to HR
                company=company,        # Link to Company
                section='Management',   # Default Section
                is_approved=True        # HR is auto-approved
            )

            self.stdout.write(self.style.SUCCESS(f"Successfully created HR '{username}' for '{company_name}'!"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))