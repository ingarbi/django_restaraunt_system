import random
from datetime import timedelta, datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from faker import Faker
from orders.models import Category, MenuItem, Order, OrderItem
import pytz

Order._meta.get_field('created_at').auto_now_add = False

User = get_user_model()
fake = Faker('ru_RU')

class Command(BaseCommand):
    help = 'Generate fake orders for testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=50,
            help='Number of orders to create (default: 50)'
        )
        parser.add_argument(
            '--year',
            type=int,
            help='Specific year to create orders (e.g., 2024)'
        )
        parser.add_argument(
            '--month',
            type=int,
            help='Specific month to create orders (1-12) - requires --year'
        )
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date in format YYYY-MM-DD (e.g., 2024-01-01)'
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date in format YYYY-MM-DD (e.g., 2024-12-31)'
        )
        parser.add_argument(
            '--months-back',
            type=int,
            help='Number of months back from SPECIFIC DATE (use with --from-date)'
        )
        parser.add_argument(
            '--from-date',
            type=str,
            help='Base date for months-back calculation (e.g., 2025-12-31)'
        )

    def handle(self, *args, **options):
        count = options['count']
        
        # Определяем диапазон дат
        start_date, end_date = self.get_date_range(options)
        
        self.stdout.write(self.style.SUCCESS(f'📅 Creating orders from {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")}'))
        self.stdout.write(f'📊 Total days: {(end_date - start_date).days + 1}')
        
        # Проверяем наличие данных
        if not Category.objects.exists():
            self.stdout.write(self.style.WARNING('No categories found. Creating sample categories...'))
            self.create_categories()
        
        if not MenuItem.objects.exists():
            self.stdout.write(self.style.WARNING('No menu items found. Creating sample menu items...'))
            self.create_menu_items()
        
        if not User.objects.exists():
            self.stdout.write(self.style.WARNING('No users found. Creating sample users...'))
            self.create_users()
        
        users = list(User.objects.all())
        menu_items = list(MenuItem.objects.all())
        
        if not menu_items:
            self.stdout.write(self.style.ERROR('No menu items available!'))
            return
        
        # Создаем заказы
        total_days = (end_date - start_date).days + 1
        orders_per_day = max(1, count // total_days)
        
        created_count = 0
        
        for day_offset in range(total_days):
            current_date = start_date + timedelta(days=day_offset)
            
            daily_orders = orders_per_day
            
            # Добавляем вариации
            if random.random() > 0.7:
                daily_orders += random.randint(1, 3)
            elif random.random() > 0.8 and daily_orders > 1:
                daily_orders -= random.randint(1, 2)
            
            # Больше заказов в выходные
            if current_date.weekday() in [5, 6]:
                daily_orders = int(daily_orders * 1.5)
            
            for _ in range(daily_orders):
                if created_count >= count:
                    break
                
                random_hour = random.randint(10, 23)
                random_minute = random.randint(0, 59)
                order_time = current_date.replace(hour=random_hour, minute=random_minute, second=random.randint(0, 59))
                
                self.create_fake_order(users, menu_items, order_time)
                created_count += 1
            
            if created_count >= count:
                break
        
        self.stdout.write(self.style.SUCCESS(f'\n✅ Successfully created {created_count} orders!'))
        self.show_statistics(start_date, end_date)
    
    def get_date_range(self, options):
        """Определяет диапазон дат на основе параметров"""
        msk_tz = pytz.timezone('Europe/Moscow')
        
        # Приоритет 1: Прямое указание start-date и end-date
        if options['start_date'] and options['end_date']:
            start = datetime.strptime(options['start_date'], '%Y-%m-%d')
            end = datetime.strptime(options['end_date'], '%Y-%m-%d')
            start = msk_tz.localize(start.replace(hour=0, minute=0, second=0))
            end = msk_tz.localize(end.replace(hour=23, minute=59, second=59))
            return start, end
        
        # Приоритет 2: Год и месяц
        if options['year'] and options['month']:
            start = datetime(options['year'], options['month'], 1)
            if options['month'] == 12:
                end = datetime(options['year'] + 1, 1, 1) - timedelta(days=1)
            else:
                end = datetime(options['year'], options['month'] + 1, 1) - timedelta(days=1)
            start = msk_tz.localize(start.replace(hour=0, minute=0, second=0))
            end = msk_tz.localize(end.replace(hour=23, minute=59, second=59))
            return start, end
        
        # Приоритет 3: Только год
        if options['year']:
            start = datetime(options['year'], 1, 1)
            end = datetime(options['year'], 12, 31)
            start = msk_tz.localize(start.replace(hour=0, minute=0, second=0))
            end = msk_tz.localize(end.replace(hour=23, minute=59, second=59))
            return start, end
        
        # Приоритет 4: months-back от определенной даты
        if options['months_back'] and options['from_date']:
            base_date = datetime.strptime(options['from_date'], '%Y-%m-%d')
            base_date = msk_tz.localize(base_date)
            end = base_date
            start = end - timedelta(days=options['months_back'] * 30)
            return start, end
        
        # Приоритет 5: Только months-back (от текущей даты)
        if options['months_back']:
            end = timezone.now()
            start = end - timedelta(days=options['months_back'] * 30)
            return start, end
        
        # По умолчанию: последние 3 месяца от текущей даты
        end = timezone.now()
        start = end - timedelta(days=90)
        return start, end
    
    def show_statistics(self, start_date, end_date):
        """Показывает статистику"""
        self.stdout.write('\n📊 Statistics by month:')
        
        orders = Order.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
        
        stats = {}
        for order in orders:
            month_key = order.created_at.strftime('%Y-%m')
            month_name = order.created_at.strftime('%B %Y')
            if month_key not in stats:
                stats[month_key] = {'name': month_name, 'count': 0, 'total': 0}
            stats[month_key]['count'] += 1
            stats[month_key]['total'] += order.total_sum
        
        for month_key, data in sorted(stats.items()):
            self.stdout.write(f'  {data["name"]}: {data["count"]} orders, total: {data["total"]} руб.')
        
        total_sum = sum(o.total_sum for o in orders)
        self.stdout.write(f'\n📈 Total for period: {orders.count()} orders, {total_sum} руб.')
    
    def create_categories(self):
        categories = ['Супы', 'Салаты', 'Горячие блюда', 'Десерты', 'Напитки', 'Закуски', 'Пицца']
        for cat_name in categories:
            Category.objects.get_or_create(name=cat_name)
        self.stdout.write(f'✓ Created {len(categories)} categories')
    
    def create_menu_items(self):
        menu_data = [
            ('Борщ', 250, 'Супы'),
            ('Солянка', 280, 'Супы'),
            ('Том Ям', 350, 'Супы'),
            ('Цезарь', 350, 'Салаты'),
            ('Греческий салат', 300, 'Салаты'),
            ('Оливье', 280, 'Салаты'),
            ('Стейк из говядины', 650, 'Горячие блюда'),
            ('Котлета по-киевски', 380, 'Горячие блюда'),
            ('Лосось на гриле', 550, 'Горячие блюда'),
            ('Паста Карбонара', 420, 'Горячие блюда'),
            ('Чизкейк', 250, 'Десерты'),
            ('Тирамису', 280, 'Десерты'),
            ('Медовик', 220, 'Десерты'),
            ('Капучино', 180, 'Напитки'),
            ('Чай', 120, 'Напитки'),
            ('Кофе', 150, 'Напитки'),
            ('Морс', 130, 'Напитки'),
            ('Брускетта', 200, 'Закуски'),
            ('Картофель фри', 150, 'Закуски'),
            ('Маргарита', 400, 'Пицца'),
            ('Пепперони', 480, 'Пицца'),
            ('Четыре сыра', 520, 'Пицца'),
        ]
        
        for name, price, category_name in menu_data:
            category = Category.objects.get(name=category_name)
            MenuItem.objects.get_or_create(
                name=name,
                defaults={'price': price, 'category': category}
            )
        
        self.stdout.write(f'✓ Created {len(menu_data)} menu items')
    
    def create_users(self):
        if not User.objects.filter(username='cashier1').exists():
            User.objects.create_user(username='cashier1', password='123')
        if not User.objects.filter(username='cashier2').exists():
            User.objects.create_user(username='cashier2', password='123')
        self.stdout.write('✓ Created users')
    
    def create_fake_order(self, users, menu_items, created_at):
        """Создает заказ"""
        
        # Для старых заказов (2024, 2025) - все завершены
        now = timezone.now()
        days_old = (now - created_at).days
        
        if days_old > 365:  # Старше года
            status = random.choice(['done', 'delivered', 'cancelled'])
            paid = status != 'cancelled'
        elif days_old > 180:
            status = random.choice(['done', 'delivered'])
            paid = True
        else:
            status = random.choice(['pending', 'done', 'delivered'])
            paid = status in ['done', 'delivered']
        
        order_type = random.choice(['dine_in', 'takeaway', 'delivery'])
        payment_type = random.choice(['cash', 'online'])
        
        phone_number = None
        name = None
        address = None
        table_number = None
        
        if order_type == 'dine_in':
            table_number = random.randint(1, 15)
        elif order_type == 'delivery':
            phone_number = fake.phone_number()
            name = fake.first_name()
            address = fake.address()
        elif order_type == 'takeaway':
            phone_number = fake.phone_number()
            name = fake.first_name()
        
        order = Order.objects.create(
            discount=random.choice([0, 5, 10, 15]) if random.random() > 0.7 else 0,
            created_at=created_at,
            status=status,
            order_type=order_type,
            payment_type=payment_type,
            phone_number=phone_number,
            name=name,
            address=address,
            table_number=table_number,
            created_by=random.choice(users) if random.random() > 0.2 else None,
            paid=paid,
        )
        
        num_items = random.randint(1, 5)
        selected_items = random.sample(menu_items, min(num_items, len(menu_items)))
        total_sum = 0
        
        for menu_item in selected_items:
            quantity = random.randint(1, 3)
            OrderItem.objects.create(
                order=order,
                menu_item=menu_item,
                quantity=quantity
            )
            total_sum += menu_item.price * quantity
        
        if order.discount > 0:
            total_sum = int(total_sum * (100 - order.discount) / 100)
        
        order.total_sum = total_sum
        order.save()