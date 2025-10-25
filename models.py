from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import BigInteger
from flask_login import UserMixin
from datetime import datetime
from zoneinfo import ZoneInfo
PDT = ZoneInfo("America/Los_Angeles")

db = SQLAlchemy()

class Badge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=False)
    icon_url = db.Column(db.String(255), nullable=True)
    user_badges = db.relationship('UserBadge', backref='badge', lazy=True)
    tooltip = db.Column(db.String(255), nullable=True, unique=True) 
    badge_type = db.Column(db.String(50))  # program, upvote, comment
    required_count = db.Column(db.Integer)

class UserBadge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    badge_id = db.Column(db.Integer, db.ForeignKey('badge.id'), nullable=False)
    awarded_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('user_id', 'badge_id', name='_user_badge_uc'),)


class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    activity_date = db.Column(db.Date, nullable=False)

class Program(db.Model):
    id = db.Column(db.BigInteger, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    controls = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(256), nullable=True)
    program_url = db.Column(db.String(512), nullable=True)  
    developer = db.Column(db.String(80), nullable=False)
    version = db.Column(db.String(20), nullable=False, default='1.0.0')
    last_updated = db.Column(db.DateTime, nullable=False)
    mod_perms = db.Column(db.String(120), nullable=True)
    likes = db.Column(db.Integer, nullable=False, default=0)
    dislikes = db.Column(db.Integer, nullable=False, default=0)
    views = db.Column(db.Integer, nullable=False, default=0) 
    is_featured = db.Column(db.Boolean, default=False)

    @property
    def clean_program_url(self):
        if not self.program_url:
            return None
        return self.program_url.replace('https://makecore.org/program/', '')


class ProgramView(db.Model):
    __tablename__ = 'program_view'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    program_id = db.Column(db.BigInteger, db.ForeignKey('program.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('user_id', 'program_id', name='_user_program_uc'),)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(512), nullable=True)  # Made nullable for OAuth users
    profile_pic_name = db.Column(db.String(128), nullable=True)  
    profile_pic_url = db.Column(db.String(255), nullable=True)  
    bio = db.Column(db.Text, nullable=True)  
    rating = db.Column(db.Float, default=1200)  
    views = db.Column(db.Integer, default=0)  

    # Google OAuth fields
    google_id = db.Column(db.String(100), unique=True, nullable=True)
    is_verified = db.Column(db.Boolean, default=False)

    show_ads = db.Column(db.Boolean, default=False)

    games = db.relationship('Game', backref='creator', lazy=True)
    studios = db.relationship('Studio', backref='owner', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)
    likes = db.relationship('Like', backref='user', lazy=True)

    badges = db.relationship('UserBadge', backref='user', lazy=True)

    followers = db.relationship(
        'Follows',
        foreign_keys='Follows.followed_id',
        backref='followed',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    following = db.relationship(
        'Follows',
        foreign_keys='Follows.follower_id',
        backref='follower',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    notifications = db.relationship('Notification', backref='user', lazy=True, cascade='all, delete-orphan')

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False) 
    message = db.Column(db.Text, nullable=False)
    related_url = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(PDT))
    is_read = db.Column(db.Boolean, default=False)


class Follows(db.Model):
    __tablename__ = 'follows'
    follower_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    followed_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(PDT))

class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    published = db.Column(db.Boolean, default=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    studio_id = db.Column(db.Integer, db.ForeignKey('studio.id'), nullable=True)
    comments = db.relationship('Comment', backref='game', lazy=True)
    likes = db.relationship('Like', backref='game', lazy=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Studio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    thumbnail_url = db.Column(db.String(256), nullable=True)
    visibility = db.Column(db.String(10), nullable=False, default='public')  # 'public' or 'private'
    anyone_can_add = db.Column(db.Boolean, default=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    memberships = db.relationship('StudioMembership', backref='studio', lazy=True, cascade='all, delete-orphan')
    projects = db.relationship('StudioProject', backref='studio', lazy=True, cascade='all, delete-orphan')
    comments = db.relationship('StudioComment', backref='studio', lazy=True, cascade='all, delete-orphan')

class StudioMembership(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    studio_id = db.Column(db.Integer, db.ForeignKey('studio.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'creator', 'manager', 'contributor'
    invited = db.Column(db.Boolean, default=False)
    accepted = db.Column(db.Boolean, default=False)
    user = db.relationship('User', backref='studio_memberships', lazy=True)
    __table_args__ = (db.UniqueConstraint('user_id', 'studio_id', name='_user_studio_uc'),)

class StudioProject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    studio_id = db.Column(db.Integer, db.ForeignKey('studio.id'), nullable=False)
    program_id = db.Column(db.BigInteger, db.ForeignKey('program.id'), nullable=False)
    added_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('studio_id', 'program_id', name='_studio_program_uc'),)

class StudioComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    studio_id = db.Column(db.Integer, db.ForeignKey('studio.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('studio_comment.id'), nullable=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False, default='active')  # 'active', 'flagged', 'hidden'
    upvotes = db.Column(db.Integer, nullable=False, default=0)
    downvotes = db.Column(db.Integer, nullable=False, default=0)

    replies = db.relationship('StudioComment', backref=db.backref('parent', remote_side=[id]), lazy=True, cascade='all, delete-orphan')

class StudioActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    studio_id = db.Column(db.Integer, db.ForeignKey('studio.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('program.id'), nullable=True)
    action = db.Column(db.String(16), nullable=False)  # 'add' or 'remove'
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class StudioCommentVote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    comment_id = db.Column(db.Integer, db.ForeignKey('studio_comment.id'), nullable=False)
    vote_type = db.Column(db.String(10), nullable=False)  # 'up' or 'down'
    __table_args__ = (db.UniqueConstraint('user_id', 'comment_id', name='_user_comment_uc'),)


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)

class UserProgramTier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    program_id = db.Column(db.BigInteger, db.ForeignKey('program.id'), nullable=False)
    tier = db.Column(db.String(8), nullable=False, default='N/A')
    __table_args__ = (db.UniqueConstraint('user_id', 'program_id', name='_user_program_uc'),)

class ProgramVote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    program_id = db.Column(db.BigInteger, db.ForeignKey('program.id'), nullable=False)
    vote_type = db.Column(db.String(10), nullable=False)  # 'up' or 'down'
    __table_args__ = (db.UniqueConstraint('user_id', 'program_id', name='_user_program_vote_uc'),)

class ProgramComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    program_id = db.Column(db.BigInteger, db.ForeignKey('program.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class MakeJam(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='upcoming')  # 'upcoming', 'active', 'ended', 'judging', 'completed'
    thumbnail = db.Column(db.String(255), nullable=True) # url
    ratings_finalized = db.Column(db.Boolean, default=False, nullable=False)
    ratings_finalized_at = db.Column(db.DateTime, nullable=True)  
    submissions = db.relationship('MakeJamSubmission', backref='jam', lazy=True, cascade='all, delete-orphan')

    def end_jam(self):
        self.status = 'ended'
        self.ratings_finalized = True
        self.ratings_finalized_at = datetime.utcnow()
        

        submissions = MakeJamSubmission.query.filter_by(jam_id=self.id)\
            .order_by(MakeJamSubmission.score.desc())\
            .all()
            

        MakeJamLeaderboard.query.filter_by(jam_id=self.id).delete()
        
        # Create new leaderboard entries
        for position, submission in enumerate(submissions, 1):
            leaderboard_entry = MakeJamLeaderboard(
                jam_id=self.id,
                user_id=submission.user_id,
                position=position,
                score=submission.score or 0,
                rating_before=submission.rating_before,
                rating_after=submission.rating_after,
                rating_change=submission.rating_change
            )
            db.session.add(leaderboard_entry)
        
        db.session.commit()
    
    def get_leaderboard(self):
        return MakeJamLeaderboard.query\
            .filter_by(jam_id=self.id)\
            .order_by(MakeJamLeaderboard.position)\
            .all()
            
    def get_leaderboard_with_users(self):
        return db.session.query(
            MakeJamLeaderboard,
            User
        ).join(
            User,
            User.id == MakeJamLeaderboard.user_id
        ).filter(
            MakeJamLeaderboard.jam_id == self.id
        ).order_by(
            MakeJamLeaderboard.position
        ).all()

class MakeJamLeaderboard(db.Model):
    __tablename__ = 'makejam_leaderboard'
    
    id = db.Column(db.Integer, primary_key=True)
    jam_id = db.Column(db.Integer, db.ForeignKey('make_jam.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    position = db.Column(db.Integer, nullable=False) 
    score = db.Column(db.Float, nullable=False)
    rating_before = db.Column(db.Float, nullable=True)
    rating_after = db.Column(db.Float, nullable=True)
    rating_change = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='leaderboard_entries')
    jam = db.relationship('MakeJam', backref='leaderboard_entries')
    
    __table_args__ = (
        db.UniqueConstraint('jam_id', 'position', name='_jam_position_uc'),
    )

class SubmissionScore(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    jam_id = db.Column(db.Integer, db.ForeignKey('make_jam.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class MakeJamSubmission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    score = db.Column(db.Integer, nullable=True)
    jam_id = db.Column(db.Integer, db.ForeignKey('make_jam.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    project_title = db.Column(db.String(120), nullable=False)
    project_link = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='makejam_submissions')
    rating_before = db.Column(db.Float, nullable=True)  # User's rating before this submission
    rating_after = db.Column(db.Float, nullable=True)   # User's rating after this submission
    rating_change = db.Column(db.Float, nullable=True)   # Change in rating from this submission
    __table_args__ = (db.UniqueConstraint('jam_id', 'user_id', name='_jam_user_uc'),)

    # Theme (25 total)
    theme_use = db.Column(db.Integer, nullable=True)  # Uses the Theme often (15)
    theme_build = db.Column(db.Integer, nullable=True)  # Built Around the Theme (10)
    
    # Art (15 total)
    art_style = db.Column(db.Integer, nullable=True)  # Consistent Art Style (10)
    art_originality = db.Column(db.Integer, nullable=True)  # Doesn't Copy other Art (5)
    
    # Gameplay (30 total)
    gameplay = db.Column(db.Integer, nullable=True)  # Fun and Engaging (15)
    gameplay_originality = db.Column(db.Integer, nullable=True)  # Unique and Creative (10)
    controls = db.Column(db.Integer, nullable=True)  # Intuitive and Responsive (5)
    
    # Polish & Experience (20 total)
    sound_design = db.Column(db.Integer, nullable=True)  # Enhances the Experience (5)
    polish = db.Column(db.Integer, nullable=True)  # Few to No Bugs (5)
    replayability = db.Column(db.Integer, nullable=True)  # Encourages Multiple Plays (5)
    theme_interpretation = db.Column(db.Integer, nullable=True)  # Creative Take on the Theme (10)
    
    # Overall (5 total)
    overall_enjoyment = db.Column(db.Integer, nullable=True)  # How Much Fun Was It? (5)
    # total_score property
    @property
    def total_score(self):
        fields = [
            # Theme (25)
            self.theme_use, self.theme_build,
            # Art (15)
            self.art_style, self.art_originality,
            # Gameplay (30)
            self.gameplay, self.gameplay_originality, self.controls,
            # Polish & Experience (20)
            self.sound_design, self.polish, self.replayability, self.theme_interpretation,
            # Overall (5)
            self.overall_enjoyment
        ]
        return sum(f or 0 for f in fields)