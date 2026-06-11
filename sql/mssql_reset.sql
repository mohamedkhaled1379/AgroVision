-- AgroVision AI — reset SQL Server tables before full re-import

IF OBJECT_ID(N'dbo.analysis_bookings', N'U') IS NOT NULL DROP TABLE dbo.analysis_bookings;
IF OBJECT_ID(N'dbo.iot_readings', N'U') IS NOT NULL DROP TABLE dbo.iot_readings;
IF OBJECT_ID(N'dbo.post_reactions', N'U') IS NOT NULL DROP TABLE dbo.post_reactions;
IF OBJECT_ID(N'dbo.post_replies', N'U') IS NOT NULL DROP TABLE dbo.post_replies;
IF OBJECT_ID(N'dbo.post_likes', N'U') IS NOT NULL DROP TABLE dbo.post_likes;
IF OBJECT_ID(N'dbo.friend_requests', N'U') IS NOT NULL DROP TABLE dbo.friend_requests;
IF OBJECT_ID(N'dbo.friendships', N'U') IS NOT NULL DROP TABLE dbo.friendships;
IF OBJECT_ID(N'dbo.messages', N'U') IS NOT NULL DROP TABLE dbo.messages;
IF OBJECT_ID(N'dbo.posts', N'U') IS NOT NULL DROP TABLE dbo.posts;
IF OBJECT_ID(N'dbo.history', N'U') IS NOT NULL DROP TABLE dbo.history;
IF OBJECT_ID(N'dbo.site_settings', N'U') IS NOT NULL DROP TABLE dbo.site_settings;
IF OBJECT_ID(N'dbo.users', N'U') IS NOT NULL DROP TABLE dbo.users;
GO
