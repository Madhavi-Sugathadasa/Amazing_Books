import os, hashlib, requests

from flask import Flask, render_template, session, request, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from math import floor

app = Flask(__name__)

# Check for environment variables
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")
if not os.getenv("GOODREADS_API_KEY"):
    raise RuntimeError("GOODREADS_API_KEY is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

@app.route("/")
def index():
    #clear session variables
    session["user_id"] = None
    session["username"] = None
    session["book_id"] = None
    session["work_rating_count"] = None
    session["average_rating"] = None
    session["average_rating_int"] = None
    
    return render_template("index.html")

@app.route("/register", methods=["POST"])
def register():
    """Register a new user"""
    username = request.form.get("username")
    password = request.form.get("password")
    confirm_password = request.form.get("confirmpassword")
    
    #check required fields entered
    if username is None or (len(username.strip()) == 0):
         return render_template("index.html", message_register="Please enter username field.", message_danger=1 )
    if password is None or (len(password.strip()) == 0):
         return render_template("index.html", message_register="Please enter password field.", message_danger=1)
    if password is None or (len(password.strip()) == 0):
         return render_template("index.html", message_register="Please enter confirm password field.", message_danger=1)
    
    #check password and confirm password fiels are match
    if password != confirm_password:
        return render_template("index.html", message_register="Those passwords didn't match. Try Again", message_danger=1, )
    
    #make username not case sensitive
    username = username.lower()
    
    # check wheather user already exists.
    if db.execute("SELECT * FROM users WHERE username = :username", {"username": username}).rowcount != 0:
        return render_template("index.html", message_register="That username is taken. Try another.", message_danger=1)
    
    #make passwors hash with md5
    password_hash = hashlib.md5(password.encode())
    db.execute("INSERT INTO users (username, password) VALUES (:username, :password)",
            {"username": username, "password": password_hash.hexdigest()})
    db.commit()
    return render_template("index.html", message_register="You have successfully registered.", message_danger=0)


@app.route("/login", methods=["POST"])
def login():
    """User Login"""
    
    username = request.form.get("username")
    password = request.form.get("password")
    
    #check required fields entered
    if username is None or (len(username.strip()) == 0):
         return render_template("index.html", message_login="Please enter username field.")
    if password is None or (len(password.strip()) == 0):
         return render_template("index.html", message_login="Please enter password field.")
    
    #create passowrd hash
    password_hash = hashlib.md5(password.encode())
    
    #make username not case sensitive
    username = username.lower()
    
    user = db.execute("SELECT * FROM users WHERE username = :username AND password = :password", {"username": username, "password": password_hash.hexdigest() }).fetchone()
    
    if user is None:
         return render_template("index.html", message_login = "Invalid username or password")
    
    #set session variables
    session["user_id"] = user.id
    session["username"] = user.username
    
    return render_template("welcome.html", username = session["username"])

@app.route("/logout")
def logout():
    """User logout"""
    
    #clear session variables
    session["user_id"] = None
    session["username"] = None
    session["book_id"] = None
    session["work_rating_count"] = None
    session["average_rating"] = None
    session["average_rating_int"] = None
    
    return render_template("index.html")


@app.route("/home")
def home():
    #set book id to None and other goodreads API raitings to None
    session["book_id"] = None
    session["work_rating_count"] = None
    session["average_rating"] = None
    session["average_rating_int"] = None
    
    #check user is logged in
    if session["user_id"] is None:
        return render_template("index.html")
    
    return render_template("welcome.html", username = session["username"])


@app.route("/search", methods=["POST"])
def search():
    """Search Books"""
    #set book id to None and other goodreads API raitings to None
    session["book_id"] = None
    session["work_rating_count"] = None
    session["average_rating"] = None
    session["average_rating_int"] = None
    
    #check user is logged in
    if session["user_id"] is None:
        return render_template("index.html")
    
    search = str(request.form.get("search"))
    search_type = request.form.get("type")
    
    #check search field is not empty
    if search is None or (len(search.strip()) == 0):
        return render_template("welcome.html", message = "Please enter search field", username = session["username"] )
    
    #check search type field is not empty
    if search_type is None or (len(search_type.strip()) == 0) or (search_type != "all" and search_type != "isbn" and search_type != "author" and search_type != "title"):
        return render_template("welcome.html", message = "Please select search type", username = session["username"] )

    if (search_type == "isbn"):
        books = db.execute("SELECT * FROM books WHERE isbn LIKE :isbn ORDER BY title", {"isbn": "%"+search+"%" }).fetchall();
    elif (search_type == "author"):
        books = db.execute("SELECT * FROM books WHERE LOWER(author) LIKE :author ORDER BY title", {"author": "%"+search.lower()+"%" }).fetchall();
    elif (search_type == "title"):
        books = db.execute("SELECT * FROM books WHERE LOWER(title) LIKE :title ORDER BY title", {"title":  "%"+search.lower()+"%"}).fetchall();
    else:
        books = db.execute("SELECT * FROM books WHERE isbn LIKE :isbn OR LOWER(title) LIKE :title OR LOWER(author) LIKE :author ORDER BY title", {"isbn": "%"+search+"%", "title":  "%"+search.lower()+"%", "author": "%"+search.lower()+"%" }).fetchall();
        
    
    if books is None or (len(books) == 0):
        return render_template("welcome.html", message = "Your search - \""+search+ "\" - did not match any books." , username = session["username"], search_type = search_type, search = search)
    
    
    return render_template("welcome.html", message = "Search Results : "+str(len(books))+" matching books found.", books=books, username= session["username"], search_type = search_type, search = search)


@app.route("/books/<int:book_id>")
def book(book_id):
    """Lists details about a single book."""

    #check user is logged in
    if session["user_id"] is None:
        return render_template("index.html")
    
    # Make sure book exists.
    book = db.execute("SELECT * FROM books WHERE id = :id", {"id": book_id}).fetchone()
    if book is None:
        return render_template("error.html", message="No results Found.", username= session["username"])

    # Get all reviews with user for each review
    reviews = db.execute("SELECT review, rating, username FROM reviews JOIN users ON reviews.user_id = users.id WHERE book_id = :book_id",{"book_id": book.id}).fetchall()
    
    #check ratings on goodreads API
    res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": os.getenv("GOODREADS_API_KEY"), "isbns": book.isbn})
    if res.status_code != 200:
        raise Exception("ERROR: API request unsuccessful.")
    data = res.json()
   
    #read json
    work_rating_count= data["books"][0]["work_ratings_count"]
    average_rating= data["books"][0]["average_rating"]
    average_rating_int = int(floor(float(average_rating)))
    
    work_rating_count =format(int(work_rating_count), ',d')
    
    session["book_id"] = book.id
    session["work_rating_count"] = work_rating_count
    session["average_rating"] = average_rating
    session["average_rating_int"] = average_rating_int

    return render_template("book.html", book=book, reviews=reviews, work_rating_count=work_rating_count, average_rating=average_rating, average_rating_int=average_rating_int, username= session["username"])


@app.route("/review", methods=["POST"])
def review():
    """Add a review"""

    user_id = session["user_id"]
    #if session expired
    if session["user_id"] is None:
        return render_template("index.html")
    book_id = session["book_id"]
    
    book = db.execute("SELECT * FROM books WHERE id = :id", {"id": book_id}).fetchone()
    if book is None:
        return render_template("error.html", message="No Results Found.", username= session["username"])
    
    # Get all reviews.
    reviews = db.execute("SELECT review, rating, username FROM reviews JOIN users ON reviews.user_id = users.id WHERE book_id = :book_id",{"book_id": book.id}).fetchall()
    
    #get ratings on goodreads API from session
    work_rating_count = session["work_rating_count"]
    average_rating = session["average_rating"]
    average_rating_int = session["average_rating_int"]
    
    
    
    if db.execute("SELECT * FROM reviews WHERE book_id = :book_id AND user_id = :user_id", {"book_id": book_id , "user_id": user_id}).rowcount > 0:
        return render_template("book.html", book=book, reviews=reviews, work_rating_count=work_rating_count, average_rating=average_rating, average_rating_int=average_rating_int, message="You have already added a review for this book.",  username= session["username"], message_danger=1)
    
     #get the review text from request
    review = request.form.get("review")
    if review is None or (len(review.strip()) == 0):
        session["book_id"] = book_id
        return render_template("book.html", book=book, reviews=reviews, work_rating_count=work_rating_count, average_rating=average_rating, average_rating_int=average_rating_int, message = "Please enter your review text.", username= session["username"], message_danger=1)
    rating = request.form.get("rating")
    #get the star rating from request
    if rating is None or (int(rating) > 5) or (int (rating) <1):
        session["book_id"] = book_id
        return render_template("book.html", book=book, reviews=reviews, work_rating_count=work_rating_count, average_rating=average_rating, average_rating_int=average_rating_int, message = "Please enter a valid star rating between 1 and 5 Inclusive.",  username= session["username"], message_danger=1)
    
    db.execute("INSERT INTO reviews (review, rating, book_id, user_id) VALUES (:review, :rating, :book_id, :user_id)",
            {"review": review, "rating": rating, "book_id": book_id, "user_id": user_id})
    db.commit()
    
    #get upto date reviews with the newly added one
    reviews = db.execute("SELECT review, rating, username FROM reviews JOIN users ON reviews.user_id = users.id WHERE book_id = :book_id",{"book_id": book.id}).fetchall()
    
    #return to book detail page
    return render_template("book.html", book=book, reviews=reviews, work_rating_count=work_rating_count, average_rating=average_rating, average_rating_int=average_rating_int, message = "Your review has been added.",  username= session["username"], message_danger=0)


@app.route("/api/<isbn>")
def book_api(isbn):
    """Books API"""

    # Make sure book exists.
    book = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn": isbn}).fetchone()
    if book is None:
        return jsonify({"error": "ISBN not found"}), 404
    #get review count   
    review_count = db.execute("SELECT * FROM reviews WHERE book_id = :book_id", {"book_id": book.id}).rowcount
    #get average count    
    average_score = db.execute("SELECT AVG(rating) FROM reviews WHERE book_id = :book_id", {"book_id": book.id}).fetchone()
    print(list(average_score))
    if average_score.avg is None:
        average_score = 0
    
    #round average score to two decimal points
    if (average_score != 0):
        average_score = round(float(average_score.avg), 2)
    
    return jsonify ({
        "title": book.title,
        "author": book.author,
        "year": book.year,
        "isbn": book.isbn,
        "review_count": review_count, 
        "average_score": average_score
    })
    


