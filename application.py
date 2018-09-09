import os
import requests

from flask import Flask, session, render_template, request, redirect, url_for, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/")
def funbooks():
    return render_template("funbooks.html")


@app.route("/Registration", methods=["POST","GET"])
def Registration():
    """ register a user """

    if request.method == "GET":
        return redirect(url_for('funbooks'))

    try:
        U_name = str(request.form.get("name"))
        U_password = str(request.form.get("password"))
        U_email = str(request.form.get("email"))
        U_phone = int(request.form.get("phone_number"))
    except ValueError:
        return render_template("message.html", message="Something went Invalid! Try again!", subject="failure")
    else:
        user = db.execute("SELECT id FROM users WHERE name=:name AND email=:email ",
                            {"name": U_name, "email": U_email}).fetchone()
        if user == None:
            db.execute("INSERT INTO users (name, password, email, phone_number) VALUES (:user, :password, :email, :phone_number)",
                        {"user": U_name, "password": U_password, "email": U_email, "phone_number": U_phone})
            print("done!!!!!")
            db.commit()
            return render_template("message.html", message="Account successfully created.", subject="success")
        else:
            return render_template("message.html", message="Account already exists!", subject="failure")


@app.route("/Login", methods=["POST","GET"])
def Login():
    """ login """

    if request.method == "GET":
        return redirect(url_for('funbooks'))

    session["user_id"]=[]

    try:
        U_email = str(request.form.get("email"))
        U_password = str(request.form.get("password"))
    except ValueError:
        return render_template("message.html", message="The username or password you entered is invalid!", subject="failure")
    else:
        user = db.execute("SELECT * FROM users WHERE email=:email AND password=:password ",
                            {"email": U_email, "password": U_password}).fetchone()
        if user == None:
            return render_template("message.html", message="No such account exists!", subject="failure")
        else:
            session["user_id"].append(user)
            # print(session["user_id"])
            books = db.execute("SELECT isbn, title, author, year FROM books").fetchall()
            session["user_id"].append(books)
            return render_template("books.html", books=books, user=[user[1],user[3],user[4]] )

@app.route("/Search", methods=["POST"])
def Search():
    try:
        search = str(request.form.get("search"))
    except ValueError:
        return render_template("message.html", message="Invalid text!", subject="failure")
    else:
        search = "%"+search+"%"
        user = session.get("user_id")
        info = db.execute("SELECT isbn, title, author, year FROM books WHERE (isbn ILIKE :search OR title ILIKE :search OR author ILIKE :search OR year ILIKE :search)",
         {"search": search}).fetchall()
        if len(info) == 0:
            return render_template("message.html", message="No results for this search!", subject="failure")
        elif session.get("user_id"):
            return render_template("search.html", info=info,user=[user[0][1],user[0][3],user[0][4]])
        else:
            return redirect(url_for('funbooks'))

@app.route("/Book/<string:b_isbn>/<string:b_title>/<string:b_author>/<string:b_year>")
def Book(b_isbn,b_title,b_author,b_year):
    if session.get("user_id"):
        session["book"] = b_isbn
        res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "w5LaWopIItuFL0d6L3qKQ", "isbns": b_isbn})
        if res.status_code != 200:
            return render_template("message.html", message="API request unsuccessful.", subject="failure")
        data = res.json()
        g_rating_count = data['books'][0]['work_ratings_count']
        g_avg_rating = float(data['books'][0]['average_rating'])
        g_avg = round(g_avg_rating)
        reviews = db.execute("SELECT review,rate FROM reviews WHERE book_isbn=:book_isbn",{"book_isbn": b_isbn})
        return render_template("book.html", b_isbn=b_isbn, b_title=b_title, b_author=b_author, b_year=b_year, g_rating_count=g_rating_count, g_avg_rating=g_avg_rating, g_avg=g_avg, reviews=reviews)

@app.route("/")
def Logout():
    session.pop("user_id", None)
    session.pop("book", None)
    return redirect(url_for('funbooks'))

@app.route("/home")
def home():
    data=session.get("user_id")
    if data:
        return render_template("Books.html",books=data[1],user=[data[0][1],data[0][3],data[0][4]])
    else:
        return redirect(url_for('funbooks'))

@app.route("/Submit-Review", methods=["POST","GET"])
def Review():
    if request.method == "GET":
        return redirect(url_for('funbooks'))

    try:
        review = str(request.form.get("review"))
        rate = str(request.values.get("star"))
    except ValueError:
        return render_template("message.html", message="Something went Invalid! Try again!", subject="failure")
    else:
        if session.get("user_id"):
            user_id = str(session.get("user_id")[0][0])
            book_isbn = str(session.get("book"))
            check = db.execute("SELECT review FROM reviews WHERE user_id=:user_id AND book_isbn=:book_isbn",
                                {"user_id": user_id, "book_isbn": book_isbn}).fetchone()
            if not check:
                db.execute("INSERT INTO reviews (review, user_id, book_isbn, rate) VALUES (:review, :user_id, :book_isbn, :rate)",
                            {"review": review, "user_id": user_id, "book_isbn": book_isbn, "rate": rate})
                print("done!!!!!")
                db.commit()
                return render_template("message.html", message="Review successfully submitted.", subject="success")
            else:
                return render_template("message.html", message="Review already submitted!", subject="failure")
        else:
            return redirect(url_for('funbooks'))


@app.route("/api/<string:search_item>")
def book_api(search_item):
    book = db.execute("SELECT * FROM books WHERE isbn = :search_item",
                       {"search_item": search_item}).fetchone()
    if book == None:
        return jsonify({"error": "Not Found"}), 422

    reviews = db.execute("SELECT AVG(rate),COUNT(*) FROM reviews JOIN books ON book_isbn=isbn WHERE book_isbn=:book_isbn",{"book_isbn": search_item}).fetchone()

    item = {"isbn": book[1], "title": book[2], "author": book[3], "yearvalue": book[4], "review_count":reviews[1], "average_score": round(reviews[0],2)}

    return jsonify(item)
