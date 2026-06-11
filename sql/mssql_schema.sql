-- AgroVision AI — Microsoft SQL Server schema (safe create, no drop)

IF OBJECT_ID(N'dbo.users', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.users (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        username NVARCHAR(100) NOT NULL UNIQUE,
        phone NVARCHAR(30) NULL,
        password_hash NVARCHAR(255) NOT NULL,
        role NVARCHAR(20) NOT NULL,
        profile_image NVARCHAR(255) NULL,
        created_at NVARCHAR(40) NOT NULL,
        CONSTRAINT CK_users_role CHECK (role IN ('admin', 'user', 'worker'))
    );
END
GO

IF OBJECT_ID(N'dbo.site_settings', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.site_settings (
        id INT NOT NULL PRIMARY KEY,
        instagram_url NVARCHAR(500) NOT NULL DEFAULT N'',
        whatsapp_phone NVARCHAR(50) NOT NULL DEFAULT N'',
        disease_info NVARCHAR(MAX) NOT NULL DEFAULT N'',
        indoor_info NVARCHAR(MAX) NOT NULL DEFAULT N'',
        iot_esp_ip NVARCHAR(100) NOT NULL DEFAULT N'',
        updated_at NVARCHAR(40) NOT NULL,
        CONSTRAINT CK_site_settings_id CHECK (id = 1)
    );
END
GO

IF OBJECT_ID(N'dbo.history', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.history (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        user_id INT NOT NULL,
        action NVARCHAR(100) NOT NULL,
        details NVARCHAR(MAX) NULL,
        image_file NVARCHAR(255) NULL,
        created_at NVARCHAR(40) NOT NULL,
        CONSTRAINT FK_history_user FOREIGN KEY (user_id) REFERENCES dbo.users(id)
    );
END
GO

IF OBJECT_ID(N'dbo.posts', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.posts (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        user_id INT NOT NULL,
        content NVARCHAR(MAX) NOT NULL,
        image_file NVARCHAR(255) NULL,
        created_at NVARCHAR(40) NOT NULL,
        CONSTRAINT FK_posts_user FOREIGN KEY (user_id) REFERENCES dbo.users(id)
    );
END
GO

IF OBJECT_ID(N'dbo.messages', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.messages (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        sender_id INT NOT NULL,
        receiver_id INT NOT NULL,
        content NVARCHAR(MAX) NOT NULL,
        deleted_for_sender INT NOT NULL DEFAULT 0,
        deleted_for_receiver INT NOT NULL DEFAULT 0,
        deleted_for_all INT NOT NULL DEFAULT 0,
        deleted_at NVARCHAR(40) NULL,
        created_at NVARCHAR(40) NOT NULL,
        CONSTRAINT FK_messages_sender FOREIGN KEY (sender_id) REFERENCES dbo.users(id),
        CONSTRAINT FK_messages_receiver FOREIGN KEY (receiver_id) REFERENCES dbo.users(id)
    );
END
GO

IF OBJECT_ID(N'dbo.friendships', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.friendships (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        user1_id INT NOT NULL,
        user2_id INT NOT NULL,
        created_at NVARCHAR(40) NOT NULL,
        CONSTRAINT CK_friendships_order CHECK (user1_id < user2_id),
        CONSTRAINT UQ_friendships_pair UNIQUE (user1_id, user2_id),
        CONSTRAINT FK_friendships_u1 FOREIGN KEY (user1_id) REFERENCES dbo.users(id),
        CONSTRAINT FK_friendships_u2 FOREIGN KEY (user2_id) REFERENCES dbo.users(id)
    );
END
GO

IF OBJECT_ID(N'dbo.friend_requests', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.friend_requests (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        sender_id INT NOT NULL,
        receiver_id INT NOT NULL,
        status NVARCHAR(20) NOT NULL,
        created_at NVARCHAR(40) NOT NULL,
        updated_at NVARCHAR(40) NOT NULL,
        CONSTRAINT CK_friend_requests_status CHECK (status IN ('pending', 'accepted', 'rejected')),
        CONSTRAINT UQ_friend_requests_pair UNIQUE (sender_id, receiver_id),
        CONSTRAINT FK_friend_requests_sender FOREIGN KEY (sender_id) REFERENCES dbo.users(id),
        CONSTRAINT FK_friend_requests_receiver FOREIGN KEY (receiver_id) REFERENCES dbo.users(id)
    );
END
GO

IF OBJECT_ID(N'dbo.post_likes', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.post_likes (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        post_id INT NOT NULL,
        user_id INT NOT NULL,
        created_at NVARCHAR(40) NOT NULL,
        CONSTRAINT UQ_post_likes UNIQUE (post_id, user_id),
        CONSTRAINT FK_post_likes_post FOREIGN KEY (post_id) REFERENCES dbo.posts(id),
        CONSTRAINT FK_post_likes_user FOREIGN KEY (user_id) REFERENCES dbo.users(id)
    );
END
GO

IF OBJECT_ID(N'dbo.post_replies', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.post_replies (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        post_id INT NOT NULL,
        user_id INT NOT NULL,
        content NVARCHAR(MAX) NOT NULL,
        created_at NVARCHAR(40) NOT NULL,
        CONSTRAINT FK_post_replies_post FOREIGN KEY (post_id) REFERENCES dbo.posts(id),
        CONSTRAINT FK_post_replies_user FOREIGN KEY (user_id) REFERENCES dbo.users(id)
    );
END
GO

IF OBJECT_ID(N'dbo.post_reactions', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.post_reactions (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        post_id INT NOT NULL,
        user_id INT NOT NULL,
        reaction_type NVARCHAR(20) NOT NULL,
        created_at NVARCHAR(40) NOT NULL,
        CONSTRAINT CK_post_reactions_type CHECK (reaction_type IN ('like', 'haha', 'angry', 'wow')),
        CONSTRAINT UQ_post_reactions UNIQUE (post_id, user_id),
        CONSTRAINT FK_post_reactions_post FOREIGN KEY (post_id) REFERENCES dbo.posts(id),
        CONSTRAINT FK_post_reactions_user FOREIGN KEY (user_id) REFERENCES dbo.users(id)
    );
END
GO

IF OBJECT_ID(N'dbo.iot_readings', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.iot_readings (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        user_id INT NULL,
        nitrogen FLOAT NOT NULL,
        phosphorus FLOAT NOT NULL,
        potassium FLOAT NOT NULL,
        temperature FLOAT NOT NULL,
        humidity FLOAT NOT NULL,
        rainfall FLOAT NOT NULL,
        ph FLOAT NOT NULL,
        soil_moisture FLOAT NULL,
        created_at NVARCHAR(40) NOT NULL,
        CONSTRAINT FK_iot_readings_user FOREIGN KEY (user_id) REFERENCES dbo.users(id)
    );
END
GO

IF OBJECT_ID(N'dbo.analysis_bookings', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.analysis_bookings (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        user_id INT NOT NULL,
        start_date NVARCHAR(20) NOT NULL,
        end_date NVARCHAR(20) NOT NULL,
        duration_days INT NOT NULL,
        status NVARCHAR(20) NOT NULL DEFAULT 'scheduled',
        confirmed_by INT NULL,
        confirmed_at NVARCHAR(40) NULL,
        started_at NVARCHAR(40) NULL,
        created_at NVARCHAR(40) NOT NULL,
        CONSTRAINT CK_analysis_bookings_duration CHECK (duration_days IN (7, 14, 30)),
        CONSTRAINT FK_analysis_bookings_user FOREIGN KEY (user_id) REFERENCES dbo.users(id),
        CONSTRAINT FK_analysis_bookings_worker FOREIGN KEY (confirmed_by) REFERENCES dbo.users(id)
    );
END
GO
