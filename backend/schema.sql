-- User 表 (用户表)
CREATE TABLE IF NOT EXISTS User (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    nickname TEXT,
    password TEXT NOT NULL,
    avatarUrl TEXT,
    slogan TEXT,
    coverUrl TEXT,
    email TEXT,
    createdAt DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Memo 表 (动态/朋友圈)
CREATE TABLE IF NOT EXISTS Memo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT,
    imgs TEXT,
    favCount INTEGER DEFAULT 0 NOT NULL,
    commentCount INTEGER DEFAULT 0 NOT NULL,
    userId INTEGER NOT NULL,
    createdAt DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    music163Url TEXT,
    bilibiliUrl TEXT,
    location TEXT,
    externalUrl TEXT,
    externalTitle TEXT,
    externalFavicon TEXT DEFAULT '/favicon.png' NOT NULL,
    pinned INTEGER DEFAULT 0 NOT NULL,
    ext TEXT DEFAULT '{}' NOT NULL,
    showType INTEGER DEFAULT 1 NOT NULL,
    tags TEXT,
    FOREIGN KEY (userId) REFERENCES User(id) ON DELETE CASCADE
);

-- Comment 表 (评论表)
CREATE TABLE IF NOT EXISTS Comment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    replyTo TEXT,
    replyEmail TEXT,
    username TEXT,
    email TEXT,
    website TEXT,
    createdAt DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    memoId INTEGER NOT NULL,
    author TEXT,
    FOREIGN KEY (memoId) REFERENCES Memo(id) ON DELETE CASCADE
);

-- Friend 表 (友情链接)
CREATE TABLE IF NOT EXISTS Friend (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    icon TEXT,
    url TEXT,
    desc TEXT,
    createdAt DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Archive 表 (自动归档导入记录，保证幂等)
CREATE TABLE IF NOT EXISTS Archive (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author TEXT NOT NULL,
    tweetId TEXT NOT NULL,
    date TEXT NOT NULL,
    memoId INTEGER,
    itemCount INTEGER DEFAULT 0 NOT NULL,
    createdAt DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    UNIQUE(author, tweetId)
);

-- SysConfig 表 (系统配置)
CREATE TABLE IF NOT EXISTS SysConfig (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    value TEXT,
    createdAt DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- 创建索引 (提升查询性能)
CREATE INDEX IF NOT EXISTS idx_user_username ON User(username);
CREATE INDEX IF NOT EXISTS idx_memo_userId ON Memo(userId);
CREATE INDEX IF NOT EXISTS idx_memo_createdAt ON Memo(createdAt);
CREATE INDEX IF NOT EXISTS idx_memo_pinned ON Memo(pinned);
CREATE INDEX IF NOT EXISTS idx_memo_showType ON Memo(showType);
CREATE INDEX IF NOT EXISTS idx_comment_memoId ON Comment(memoId);
CREATE INDEX IF NOT EXISTS idx_comment_createdAt ON Comment(createdAt);
CREATE INDEX IF NOT EXISTS idx_sysconfig_name ON SysConfig(name);
CREATE INDEX IF NOT EXISTS idx_archive_author_date ON Archive(author, date);
CREATE INDEX IF NOT EXISTS idx_archive_tweetId ON Archive(tweetId);

-- 插入默认管理员用户 (用户名: admin, 密码: admin123)
-- bcrypt hash for 'admin123': $2a$10$6ep6URHMaj5tnrfa0/Cccu0U5/7BStrpLDUp2.oFJ9ujyrL3P5vlO
INSERT OR IGNORE INTO User (id, username, nickname, password, avatarUrl, slogan, coverUrl)
VALUES (
    1,
    'admin',
    '管理员',
    '$2a$10$6ep6URHMaj5tnrfa0/Cccu0U5/7BStrpLDUp2.oFJ9ujyrL3P5vlO',
    '/avatar.webp',
    '系统管理员',
    '/cover.webp'
);
