from flask import redirect,	url_for, render_template,	request
from app_files import app, db, bcrypt
from app_files.forms import RegistrationForm, LoginForm, UpdateAccountForm, OrderStatusForm, NewItemForm
from app_files.db_models import User, Item, Order
from flask_login import login_user, current_user, logout_user, login_required
# secrets do hashowania nazw zdjęć - aby się nie powtarzały
import secrets
# do wyciągnięcia rozszerzenia pliku
import os
# zainstalowano Pillow - do zmiany rozmiaru obrazów
from PIL import Image

# ------------------------------------WIDOKI-----------------------------------------#

@app.route('/')
def root():
	itemsList = Item.query.all()
	return render_template('main.html', itemsList=itemsList)



@app.route('/login', methods=['GET', 'POST'])
def login():
	# sprawdza, czy użytkownik jest już zalogowany - wbudowana funkcja flask_login
	if current_user.is_authenticated:
		return redirect(url_for('root'))
	form = LoginForm()
	if form.validate_on_submit():
		user = User.query.filter_by(email=form.email.data).first()
		# wbudowana funkcja bcrypt, porównująca hasło z bd z hasłem z formularza
		if user and bcrypt.check_password_hash(user.password, form.password.data):
			# wbudowana funkcja flask-login, arg. remember pobiera z checkboxa formularza
			login_user(user, remember=form.remember.data)
			# pobiera argument next z querystringa i po zalogowaniu przekierowuje
			# od razu na żądaną stronę (gdzie wymagane było zalogowanie), nie na root
			# w login.html musi być <form action = "">, aby nie usunęło parametru next
			# get() zamiast [] - nie wyrzuci błędu tylko None, jeśli parametr nie istnieje
			next_page = request.args.get('next')
			return redirect(next_page) if next_page else redirect(url_for('root'))
		else:
			return render_template('login_failed.html')
	return render_template('login.html', form=form)



@app.route('/logout')
def logout():
	logout_user()
	return redirect(url_for('root'))



@app.route('/register', methods=['GET', 'POST'])
def register():
	# sprawdza, czy użytkownik jest już zalogowany - wbudowana funkcja flask_login
  if current_user.is_authenticated:
    return redirect(url_for('root'))
  form = RegistrationForm()
  if form.validate_on_submit():
    hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
    # user_id stworzy się automatycznie, kolejne
    user = User(username=form.username.data, email=form.email.data, password=hashed_password)
    db.session.add(user)
    db.session.commit()
    return render_template('register_ok.html')
  return render_template('register.html', form=form)



# funkcja do uploadu zdjęcia użytkownika
def save_picture(form_picture):
	# generowanie losowego hasha (8 znaków)
	random_hex = secrets.token_hex(8)
	# oddzielenie nazwy i rozszerzenia pliku
	f_name, file_extension = os.path.splitext(form_picture.filename) # _ - oznaczenie nieużywanej zmiennej
	picture_filename = random_hex + file_extension
	# określenie ścieżki zapisu plików
	picture_path = os.path.join(app.root_path, 'static/images/profile_pictures', picture_filename)
	# zmiana rozmiaru obrazu przy zapisywaniu
	output_size = (125, 125)
	resized_picture = Image.open(form_picture)
	resized_picture.thumbnail(output_size)
	# zapisywanie obrazu do folderu
	resized_picture.save(picture_path)
	# zwraca nazwę pliku, aby zapisać ją w bazie danych
	return picture_filename

@app.route('/account', methods=['GET', 'POST'])
# dekorator z flask_login
@login_required
def account():
	# brak dostępu dla admina
	if current_user.isAdmin:
		return redirect(url_for('root'))
	form = UpdateAccountForm()
	# zmiana danych użytkownika
	if form.validate_on_submit():
		# if, bo dodanie pliku obrazu nie jest wymagane
		if form.picture.data:
			# zapisanie pliku zdjęcia do /profile_pictures
			picture_file = save_picture(form.picture.data)
			# usuwanie starego zdjęcia
			if current_user.image_file != 'defaultpp.jpg':
				old_picture_path = os.path.join(app.root_path, 'static/images/profile_pictures', current_user.image_file)
				os.remove(old_picture_path)
			current_user.image_file = picture_file
			
		current_user.username = form.username.data
		current_user.email = form.email.data
		current_user.adress = form.adress.data
		current_user.phone = form.phone.data
		db.session.commit()
		# przy ładowaniu ponownie tej samej strony należy użyć redirect -
		# przy render_template po odświeżeniu strony POST będzie wysyłany ponownie (wyskoczy komunikat z pytniem o ponowne przesłanie formularza)
		return render_template('updated.html')
	# wypełnia pola formularza aktualnymi danymi
	elif request.method == 'GET':
		form.username.data = current_user.username
		form.email.data = current_user.email
		form.adress.data = current_user.adress
		form.phone.data = current_user.phone
	# określa ścieżkę do zdjęcia profilowego
	image_file = url_for('static', filename='images/profile_pictures/' + current_user.image_file)
	return render_template('account.html', form=form, image_file=image_file)



@app.route('/cart', methods=['GET', 'POST'])
# dekorator z flask_login
@login_required
def cart():
	# brak dostępu dla admina, brak reakcji na POST po kliknięciu "Zamów" przez admina
	if current_user.isAdmin:
		return redirect(url_for('root'))
	if request.method == 'POST':
		# pobranie itemID z main.html
		orderedItemID = int(request.form['orderedItemID'])
		# stworzenie obiektu zamówienia, dodanie go do bazy danych
		order = Order(itemID=orderedItemID, userID=current_user.id)
		db.session.add(order)
		db.session.commit()
	# zapytanie zamówień zalogowanego użytkownika
	# query(Order) - dostęp do Order; query(Order, Item), żeby mieć dostęp też do Item, który dołączamy joinem
	ordersList = db.session.query(Order, Item).filter(Order.userID==current_user.id).join(Item, Order.itemID==Item.id)
	return render_template('cart.html', ordersList=ordersList)



# funkcja do uploadu zdjęcia przedmiotu
def save_item_picture(form_picture):
	# generowanie losowego hasha (8 znaków)
	random_hex = secrets.token_hex(8)
	# oddzielenie nazwy i rozszerzenia pliku
	f_name, file_extension = os.path.splitext(form_picture.filename) # _ - oznaczenie nieużywanej zmiennej
	picture_filename = random_hex + file_extension
	# określenie ścieżki zapisu plików
	picture_path = os.path.join(app.root_path, 'static/images/shop', picture_filename)
	# zmiana rozmiaru obrazu przy zapisywaniu
	output_size = (700, 700)
	resized_picture = Image.open(form_picture)
	resized_picture.thumbnail(output_size)
	# zapisywanie obrazu do folderu
	resized_picture.save(picture_path)
	# zwraca nazwę pliku, aby zapisać ją w bazie danych
	return picture_filename

@app.route('/shopmanagement', methods=['GET', 'POST'])
# dekorator z flask_login
@login_required
def shopmanagement():
	if current_user.isAdmin:
		# usuwanie przedmiotu z bazy danych przez formularz z tabeli
		# try - bo w templatce są 2 formularze, obsługa error przy dodawaniu przedmiotu
		try:
			# pobranie itemID z shopmanagement.html
			deletedItemID = int(request.form['deletedItemID'])
			# zapytanie o obiekt przedmiotu w bd
			deletedItem = Item.query.filter_by(id=deletedItemID).first()
			# usunięcie zdjęcia przedmiotu
			picture_path = os.path.join(app.root_path, 'static/images/shop', deletedItem.itemImage)
			os.remove(picture_path)
			# usunięcie przedmiotu z bd
			db.session.delete(deletedItem)
			db.session.commit()
			# przy ładowaniu ponownie tej samej strony należy użyć redirect -
			# przy render_template po odświeżeniu strony POST będzie wysyłany ponownie (wyskoczy komunikat z pytniem o ponowne przesłanie formularza) i wyskoczą walidacje drugiego formularza
			return redirect(url_for('shopmanagement'))
		except:
			# dodawanie nowego przedmiotu
			# można wstawić do except, form_newItem zawsze będzie wczytany
			# należy użyć innej nazwy niż 'form', bo form jest użyty w templatce do usuwania przedmiotów
			form_newItem = NewItemForm()
			if form_newItem.validate_on_submit():
				# zapisanie pliku zdjęcia do /shop, zapisanie zmienionej nazwy pliku zdjęcia
				item_image = save_item_picture(form_newItem.itemImage.data)
				# dodanie przedmiotu do bazy danych
				item = Item(itemName=form_newItem.itemName.data, 
					itemMainDescription=form_newItem.itemMainDescription.data, 
					itemPointsDescription=form_newItem.itemPointsDescription.data, 
					itemImage=item_image, 
					itemPrice=form_newItem.itemPrice.data)
				db.session.add(item)
				db.session.commit()
				# przy ładowaniu ponownie tej samej strony należy użyć redirect -
				# przy render_template po odświeżeniu strony POST będzie wysyłany ponownie (wyskoczy komunikat z pytniem o ponowne przesłanie formularza) i w formularz pozostanie wypełniony
				return redirect(url_for('shopmanagement'))
		# lista wszystkich przedmiotów w sklepie do templatki
		itemsList = Item.query.all()
		return render_template('shopmanagement.html', itemsList=itemsList, form=form_newItem)
	else:
		return redirect(url_for('root'))



@app.route('/orders', methods=['GET', 'POST'])
# dekorator z flask_login
@login_required
def orders():
	if current_user.isAdmin:
		form = OrderStatusForm()
		# zmiana statusu zamówienia w przypadku POST
		if form.validate_on_submit():
			# pobranie numeru zamówienia, którego dotyczy zmiana
			orderID = form.orderID.data
			# zapytanie o zamówienie wg jego id
			order = db.session.query(Order).filter(Order.id==orderID).first()
			# zmiana statusu zamówienia w bazie danych
			order.status = form.status.data
			db.session.commit()
		# zapytanie wszystkich zamówień
		# query(Order) - zapytanie do Order; query(Order, Item, User), żeby mieć dostęp też do Item i User, dołączanych joinem
		ordersList = db.session.query(Order, Item, User).join(Item, Order.itemID==Item.id).join(User, Order.userID==User.id).all()
		return render_template('orders.html', ordersList=ordersList, form=form)
	else:
		return redirect(url_for('root'))