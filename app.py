from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
import os
login_attempts = {}
ALLOWED_EXTENSIONS = ['png', 'jpg', 'jpeg', 'gif', 'mp4']

import mimetypes

def validate_image(file):
    if not file:
        return False

    mime_type = mimetypes.guess_type(file.filename)[0]
    return mime_type and mime_type.startswith('image')
    
def allowed_file(filename):
    return '.' in filename and filename.split('.')[-1].lower() in ALLOWED_EXTENSIONS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
import os
import uuid
from flask_socketio import SocketIO, send

socketio = SocketIO(app)

import os

app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax'
)

# DB CONFIG
import os
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    "DATABASE_URL",
    "sqlite:///database.db"
)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB limit

db = SQLAlchemy(app)

# ================= user_idS TABLE =================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_idname = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    bio = db.Column(db.String(300), default="")
    profile_pic = db.Column(db.String(200), default="default.jpg")
    posts = db.relationship('Post', backref='author', lazy=True)

# ================= POSTS TABLE =================
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    file = db.Column(db.String(200))
    file_type = db.Column(db.String(10))

    caption = db.Column(db.String(200))
    user_id_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    likes = db.Column(db.Integer, default=0)
    category = db.Column(db.String(50), default="general")
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

# ================= COMMENTS TABLE =================
class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(300), nullable=False)
    user_id_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'))

# ================= FOLLOW TABLE =================
class Follow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    following_id = db.Column(db.Integer, db.ForeignKey('user.id'))

#==================== like teble =========
class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id_id = db.Column(db.Integer)
    post_id = db.Column(db.Integer)
    __table_args__ = (
 db.UniqueConstraint('user_id_id', 'post_id', name='unique_like'),
)
#================ Notification =============
class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)   # receiver
    message = db.Column(db.String(300))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

#=========== save post =========
class SavePost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    post_id = db.Column(db.Integer)

#================= story ============    
class Story(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    file = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=db.func.now())
# ================= HOME =================
@app.route('/home')
def home():
    if 'user_id' in session:
        return redirect('/feed')
    return redirect('/login')
#============  serach ============
@app.route('/search')
def search():
    if 'user_id' not in session:
        return redirect('/login')

    query = request.args.get('q', '').strip()

    user_ids = User.query.filter(User.user_idname.ilike(f"%{query}%")).all()

    return render_template('search.html', user_ids=user_ids, query=query)


# ================= REGISTER =================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':

        user_idname = request.form['user_idname'].lower().strip()
        password = request.form['password']

        if len(password) < 7:
            return "Password must be at least 8 characters ❌"

        file = request.files.get('profile_pic')

        existing_user_id = User.query.filter_by(user_idname=user_idname).first()
        if existing_user_id:
            return "user_idname already exists ❌"

        hashed_password = generate_password_hash(
            password,
            method='pbkdf2:sha256',
            salt_length=16
        )

        filename = "default.jpg"

        if file and file.filename != "":
            filename = str(uuid.uuid4()) + "_" + secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        new_user_id = User(
            user_idname=user_idname,
            password=hashed_password,
            profile_pic=filename
        )

        db.session.add(new_user_id)
        db.session.commit()

        # 🔥 AUTO LOGIN (IMPORTANT FIX)
        session['user_id'] = new_user_id.id
        return redirect('/feed')

    return render_template('register.html')

# ================= LOGIN =================
@app.route('/login', methods=['GET', 'POST'])
def login():

    # 🔥 AUTO LOGIN CHECK
    if 'user_id' in session:
        return redirect('/feed')

    if request.method == 'POST':
        username = request.form['user_idname'].lower().strip()
        password = request.form['password']

        user = User.query.filter_by(user_idname=username).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            return redirect('/feed')

        return "Invalid username or password ❌"

    return render_template('login.html')

@app.route('/')
def index():
    return redirect('/login')
   
# ================= FEED =================
@app.route('/feed')
def feed():
    if 'user_id' not in session:
        return redirect('/login')

    following = Follow.query.filter_by(follower_id=session['user_id']).all()
    following_list = [f.following_id for f in following]
    following_user_ids = [f.following_id for f in following]

     # include own posts also
    following_user_ids.append(session['user_id'])

    page = request.args.get('page', 1, type=int)
    posts = Post.query.filter(Post.user_id_id.in_(following_user_ids))\
    .order_by(Post.id.desc())\
    .paginate(page=page, per_page=5).items
    user_ids = {u.id: u for u in User.query.all()}
    

    comments = Comment.query.filter(Comment.post_id.in_([p.id for p in posts])).all()
 
    post_comments = {}
    for comment in comments:
     post_comments.setdefault(comment.post_id, []).append(comment)
    user_ids = {u.id: u for u in User.query.all()}
    
    return render_template(
    'feed.html',
    posts=posts,
    user_id=session['user_id'],
    post_comments=post_comments,
    user_ids=user_ids,
    following_list=following_list
)

#=========== comment ==========
@app.route('/comment/<int:post_id>', methods=['POST'])
def comment(post_id):
    if 'user_id' not in session:
        return redirect('/login')

    text = request.form['text'].strip()

    if not text:
      return redirect('/feed')

    new_comment = Comment(
        text=text,
        user_id_id=session['user_id'],
        post_id=post_id
    )

    db.session.add(new_comment)
    db.session.commit()

    return redirect('/feed')

#============== save =========
@app.route('/save/<int:post_id>')
def save_post(post_id):
    if 'user_id' not in session:
        return redirect('/login')

    exists = SavePost.query.filter_by(
        user_id=session['user_id'],
        post_id=post_id
    ).first()

    if not exists:
        db.session.add(SavePost(
            user_id=session['user_id'],
            post_id=post_id
        ))
        db.session.commit()

    return redirect('/feed')

def validate_image(file):
    if not file:
        return False

    mime_type = mimetypes.guess_type(file.filename)[0]
    return mime_type and mime_type.startswith('image')

# ================= UPLOAD =================
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'user_id' not in session:
        return redirect('/login')

    if request.method == 'POST':
        file = request.files.get('file')

        if not file:
         return "No file uploaded ❌"
        if file.filename == '':
         return "No file selected ❌"

        if not allowed_file(file.filename):
         return "File type not allowed ❌"
        
        caption = request.form['caption'].strip()

        import uuid
        filename = str(uuid.uuid4()) + "_" + secure_filename(file.filename)
        ext = filename.split('.')[-1].lower()

        if ext not in ALLOWED_EXTENSIONS:
         return "Invalid file type ❌"
        category = request.form['category']

        # upload folder ensure
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        # 🔥 FIX: file type detect karo
        ext = filename.split('.')[-1].lower()
        if ext not in ALLOWED_EXTENSIONS:
         return "Invalid file type ❌"

        if ext in ['mp4', 'mov', 'avi', 'mkv']:
            file_type = 'video'
        else:
            file_type = 'image'
            if not validate_image(file):
             return "Invalid image ❌"

        # create post
        new_post = Post(
             file=filename,
             file_type=file_type,
             caption=caption,
             user_id_id=session['user_id'],
             category=category
      )
        db.session.add(new_post)
        db.session.commit()

        return redirect('/feed')

    return render_template('upload.html')

# ================= LIKE =================
@app.route('/like/<int:post_id>')
def like(post_id):
    if 'user_id' not in session:
        return redirect('/login')

    existing = Like.query.filter_by(
        user_id_id=session['user_id'],
        post_id=post_id
    ).first()

    if existing:
        return redirect('/feed')

    post = Post.query.get(post_id)  # ✅ get once

    if not post:
        return redirect('/feed')

    # like entry
    new_like = Like(
        user_id_id=session['user_id'],
        post_id=post_id
    )
    db.session.add(new_like)

    # increase likes
    post.likes += 1

    # notification (IMPORTANT PART)
    if post.user_id_id != session['user_id']:
        notification = Notification(
            user_id=post.user_id_id,
            message="Someone liked your post ❤️"
        )
        db.session.add(notification)

    # commit everything once
    db.session.commit()

    return redirect('/feed')
#================== app ===========
@app.route('/api/feed')
def api_feed():
    posts = Post.query.order_by(Post.id.desc()).all()

    return {
        "posts": [
            {
                "id": p.id,
                "caption": p.caption,
                "likes": p.likes
            } for p in posts
        ]
    }

#=============== chat route ============
@socketio.on('message')
def handle_message(msg):
    send(msg, broadcast=True)

#============== follow route =================

@app.route('/follow/<int:user_id>')
def follow(user_id):
    if 'user_id' not in session:
        return redirect('/login')

    current_user = session['user_id']

    if current_user == user_id:
        return "You cannot follow yourself ❌"

    existing = Follow.query.filter_by(
        follower_id=current_user,
        following_id=user_id
    ).first()

    if not existing:
        new_follow = Follow(
            follower_id=current_user,
            following_id=user_id
        )
        db.session.add(new_follow)
        db.session.commit()

    return redirect('/profile/' + str(user_id))

#================ unfollow route ============

@app.route('/unfollow/<int:user_id>')
def unfollow(user_id_id):
    if 'user_id' not in session:
        return redirect('/login')

    follow = Follow.query.filter_by(
        follower_id=session['user_id'],
        following_id=user_id_id
    ).first()

    if follow:
        db.session.delete(follow)
        db.session.commit()

    return redirect('/feed')

#================ change password =============
@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'user_id' not in session:
        return redirect('/login')

    if request.method == 'POST':
        old_password = request.form['old_password']
        new_password = request.form['new_password']

        user = User.query.get(session['user_id'])

        # check old password
        if not check_password_hash(user.password, old_password):
            return "Old password wrong ❌"
        if len(new_password) < 7:
          return "Password too weak ❌"
        # update password
        user.password = generate_password_hash(new_password)
        db.session.commit()

        return "Password changed successfully ✅"

    return render_template('change_password.html')

# ==================== new return buttion =============
@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'

    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'

    return response
# ================= PROFILE =================
@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect('/login')

    user = User.query.get(session['user_id'])

    if not User:
        return redirect('/login')   # 🔥 FIX CRASH

    posts = Post.query.filter_by(user_id_id=session['user_id']).all()

    total_likes = sum(post.likes for post in posts)

    return render_template(
    'profile.html',
    user=user,
    posts=posts,
    total_likes=total_likes
)
  
#=============== other profile ===========
@app.route('/profile/<int:user_id>')
def public_profile(user_id):
    if 'user_id' not in session:
        return redirect('/login')

    user = User.query.get(user_id)

    if not user:
        return "User not found ❌"

    posts = Post.query.filter_by(user_id_id=user_id).all()

    is_following = Follow.query.filter_by(
        follower_id=session['user_id'],
        following_id=user_id
    ).first()

    return render_template(
        'profile.html',
        user=user,
        posts=posts,
        is_following=is_following
    )

#============== edit profile ==============
@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect('/login')

    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        bio = request.form['bio']
        file = request.files.get('profile_pic')

        user.bio = bio


        if file and file.filename != '':
           import uuid
           filename = str(uuid.uuid4()) + "_" + secure_filename(file.filename)
           file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

           user.profile_pic = filename # 🔥 IMPORTANT LINE
        
        db.session.commit()
        return redirect('/profile')

    return render_template('edit_profile.html', user=user)


# ================= DELETE =================
@app.route('/delete/<int:post_id>')
def delete_post(post_id):
    if 'user_id' not in session:
        return redirect('/login')

    post = Post.query.get(post_id)

    if post and post.user_id_id == session['user_id']:
         file_path = os.path.join(app.config['UPLOAD_FOLDER'], post.file)
         if os.path.exists(file_path):
          os.remove(file_path)
         db.session.delete(post)
         db.session.commit()

    return redirect('/feed')

# ================= LOGOUT =================
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ================= RUN APP =================
if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    socketio.run(app, host="0.0.0.0", port=5000)