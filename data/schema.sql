CREATE TABLE IF NOT EXISTS reminders(
    id SERIAL,
    start timestamp without time zone,
    "end" timestamp without time zone,
    "user" bigint,
    channel bigint,
    message bigint,
    content text COLLATE pg_catalog."default",
    event text COLLATE pg_catalog."default" NOT NULL,
    CONSTRAINT reminders_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS timezones(
    "user" bigint NOT NULL,
    tz text NOT NULL,
    CONSTRAINT timezones_pkey PRIMARY KEY ("user")
);

CREATE TABLE IF NOT EXISTS playlists(
    "user" bigint NOT NULL,
    name text NOT NULL,
    url text NOT NULL,
    private bool DEFAULT FALSE,
    CONSTRAINT playlists_pkey PRIMARY KEY ("user", name)
);

CREATE TABLE IF NOT EXISTS noafks(
    "user" bigint,
    CONSTRAINT noafks_pkey PRIMARY KEY ("user")
);

CREATE TABLE IF NOT EXISTS highlights(
    guild bigint,
    "user" bigint,
    word text,
    CONSTRAINT highlights_pkey PRIMARY KEY (guild, "user", word)
);

CREATE TABLE IF NOT EXISTS mentions(
    "user" bigint,
    CONSTRAINT mentions_pkey PRIMARY KEY ("user")
);

CREATE TABLE IF NOT EXISTS hlignores(
    "user" bigint,
    id bigint,
    type text,
    CONSTRAINT hlignores_pkey PRIMARY KEY ("user", id)
);

CREATE TABLE IF NOT EXISTS prefixes(
    guild bigint,
    prefix text,
    CONSTRAINT prefixes_pkey PRIMARY KEY (guild, prefix)
);

CREATE TABLE IF NOT EXISTS first_join(
    guild bigint,
    "user" bigint,
    time timestamp without time zone,
    CONSTRAINT first_join_pkey PRIMARY KEY (guild, "user")
);

CREATE TABLE IF NOT EXISTS guild_config(
    id bigint,
    human_join_role bigint,
    bot_join_role bigint,
    CONSTRAINT guild_config_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS guild_mod_config(
    id bigint,
    join_ch bigint,
    leave_ch bigint,
    mute_role bigint,
    muted bigint array,
    CONSTRAINT guild_mod_config_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS gatekeep(
    id bigint,
    by bigint,
    level text,
    CONSTRAINT gatekeep_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS name_changes(
    id bigint,
    name text,
    discrim smallint,
    changed_at timestamp without time zone,
    CONSTRAINT name_changes_pkey PRIMARY KEY (id, changed_at)
);

CREATE TABLE IF NOT EXISTS nick_changes(
    id bigint,
    guild bigint,
    name text,
    changed_at timestamp without time zone,
    CONSTRAINT nick_changes_pkey PRIMARY KEY (id, changed_at)
);

CREATE TABLE IF NOT EXISTS avatar_changes(
    id bigint,
    hash text,
    url text,
    message bigint,
    changed_at timestamp without time zone,
    CONSTRAINT avatar_changes_pkey PRIMARY KEY (id, changed_at)
);

CREATE TABLE IF NOT EXISTS blacklist(
    id bigint,
    type text,
    reason text,
    CONSTRAINT blacklist_pkey PRIMARY KEY (id)
);
