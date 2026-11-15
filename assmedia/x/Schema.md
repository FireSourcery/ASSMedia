# X bookmarks: schema

What gallery-dl 1.32.19 gives for each tweet, and where each field ends up on a bookmark page. This is the one place the page properties are defined.  

- **The source:** gallery-dl's metadata post-processor writes one JSON file per tweet:
  - `items\<id>\<id>.json` for a bookmark
  - `items\<id>\<id>.quoted.json` for a tweet fetched because a bookmark quotes it
  - `threads\<id>.json` for every tweet a thread lookup returns
- **Every field stays in that JSON,** which is never deleted, so a field that isn't a property today can still become one later. 

**Where a field can go:**
- **property `name`:** a page property
- **body:** the page text, in its sections (Earlier in the thread, Bookmarked tweet, Continuation, Quoted tweet)
- **export:** what the tagger reads (`build\export\`)
- **tool:** used by the tool, for example to assemble threads or decide on lookups, and not shown on the page
- **raw only:** kept in the JSON and nowhere else

## Native fields: the tweet

| Field                                                                            | Type                       | Meaning                                                                            | Goes to                                                             |
| -------------------------------------------------------------------------------- | -------------------------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| `tweet_id`                                                                       | int                        | the tweet's id                                                                     | property `tweet_id`, and part of `source_url`                       |
| `content`                                                                        | str                        | full text, long posts included, t.co links expanded                                | body and export                                                     |
| `date`                                                                           | str `YYYY-MM-DD hh:mm:ss`  | when it was posted                                                                 | property `published` (date only)                                    |
| `date_bookmarked`                                                                | str                        | when you bookmarked it. A quoted copy inherits the date from its quoting bookmark. | property `saved`                                                    |
| `author`                                                                         | user object                | who posted it                                                                      | see below                                                           |
| `user`                                                                           | user object                | in bookmark and thread JSON, an exact copy of `author`                             | raw only                                                            |
| `conversation_id`                                                                | int                        | the id of the thread's first tweet                                                 | tool: thread assembly                                               |
| `reply_id`                                                                       | int                        | the tweet this replies to; 0 when it isn't a reply                                 | tool: thread assembly and the lookup decision                       |
| `reply_to`                                                                       | str                        | the username replied to                                                            | tool: thread assembly                                               |
| `reply_count`                                                                    | int                        | replies at download time                                                           | tool: the lookup decision (replies > 0)                             |
| `quoted_id`                                                                      | int                        | the tweet this quotes; 0 when none                                                 | tool: finding the quoted tweet (Quoted tweet section and its media) |
| `quote_id`                                                                       | int                        | in `.quoted.json`, the quoting bookmark; 0 in bookmarks                            | tool: the `.quoted.json` split                                      |
| `quote_by`                                                                       | str                        | the quoting bookmark's author                                                      | raw only                                                            |
| `source_user`                                                                    | user object                | the account that first posted reused media ("From @…" on X)                        | export: the `source_person` role (its `name`)                       |
| `source_id`                                                                      | int                        | the tweet that first posted reused media; 0 when none                              | raw only                                                            |
| `retweet_id`                                                                     | int                        | 0 for everything saved here (retweets are skipped)                                 | raw only                                                            |
| `hashtags`                                                                       | list of str                | without `#`                                                                        | property `hashtags`, and export                                     |
| `mentions`                                                                       | list of `{id, name, nick}` | accounts @-mentioned                                                               | raw only                                                            |
| `article`                                                                        | object                     | an X Article (see below)                                                           | body and export (`article_title`, `article_text`)                   |
| `count`                                                                          | int                        | media files in the tweet                                                           | tool: the incomplete-download check                                 |
| `lang`                                                                           | str                        | X's language guess (`zxx` for no text)                                             | raw only                                                            |
| `sensitive`, `sensitive_flags`                                                   | bool or null, list or null | X's sensitive-media flag and reasons                                               | raw only                                                            |
| `birdwatch`                                                                      | str                        | a community note                                                                   | raw only                                                            |
| `source`                                                                         | str                        | the posting app ("Twitter for Android")                                            | raw only                                                            |
| `favorite_count`, `retweet_count`, `quote_count`, `bookmark_count`, `view_count` | int                        | counts at download time, frozen from then on                                       | raw only                                                            |
| `category`, `subcategory`                                                        | str                        | `twitter`, plus `bookmark` (feed) or `tweet` (lookup)                              | raw only                                                            |

**Not saved at all:** the per-file fields (`num`, `extension`, size, duration). The metadata post-processor runs once per tweet, not once per file.

## Native fields: user objects

`author`, `user` and `source_user` have the same 17 fields.

| Field                                                                                                   | Meaning                              | Goes to                                                                                                |
| ------------------------------------------------------------------------------------------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------ |
| `name`                                                                                                  | the username, without `@`            | `author.name`: property `source_author`, part of `source_url`, and export. `source_user.name`: export. |
| `nick`                                                                                                  | the display name, as X shows it      | `author.nick`: property `source_author_name`, and export                                               |
| `id`                                                                                                    | the numeric account id               | tool: the lookup's stop and media filters                                                              |
| `description`, `location`, `url`                                                                        | the profile's bio, location and link | raw only, **on purpose**: the design's anti-goal keeps profile data out of the vault                   |
| `date`, `verified`, `protected`, `profile_image`, `profile_banner`                                      | account details                      | raw only                                                                                               |
| `followers_count`, `friends_count`, `favourites_count`, `listed_count`, `media_count`, `statuses_count` | profile counts at download time      | raw only                                                                                               |

`mentions` entries carry only `id`, `name` and `nick`.

## Native fields: X Articles

| Where | Shape | Used for |
|---|---|---|
| The Bookmarks feed (`<id>.json`, `<id>.quoted.json`) | `{id, title, date, date_updated}`: the title only, with no text and no inline images | the title, until the lookup has run |
| A thread lookup (`threads\<id>.json`) | `{article_results: {result: {title, content_state, media_entities, cover_media, preview_text, metadata, ...}}}` | the title, and the full text built from `content_state`'s blocks (`assmedia/x/tweet.py`, `article_text`) |

That's why every article gets a lookup, bookmarked or quoted ([Design.md](../../Design.md#config), "Config").

## Obsidian page properties

The properties `render_x_page` writes (`assmedia/x/page.py`), in this order. Instagram's [Schema.md](../instagram/Schema.md#obsidian-page-properties) has the same table: the same properties in the same order, apart from the post's id.

**Origin:** `native` is a gallery-dl field, named under From. `derived` is worked out from fields or the downloaded files. `tagged` comes from Claude's tags file, under the rules in [Tagging.md](../../Tagging.md). `tool` is set by the tool itself.

| Property             | Origin  | From                                                       | Notes                                                                                                                                                                                                        |
| -------------------- | ------- | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `type`               | tool    | —                                                          | always `source`                                                                                                                                                                                              |
| `source`             | tool    | —                                                          | always `X`                                                                                                                                                                                                   |
| `tweet_id`           | native  | `tweet_id`                                                 | the post's id, as a quoted string, because 19-digit ids lose precision as numbers; in place of Instagram's `shortcode`                                                                                       |
| `source_url`         | derived | `author.name`, `tweet_id`                                  | `https://x.com/<author>/status/<tweet_id>`                                                                                                                                                                   |
| `source_author`      | native  | `author.name`                                              | the username, plain text; the "By creator" view groups on it                                                                                                                                                 |
| `source_author_name` | native  | `author.nick`                                              | the display name, as X shows it                                                                                                                                                                              |
| `published`          | native  | `date`                                                     | the date posted, date only                                                                                                                                                                                   |
| `saved`              | native  | `date_bookmarked`                                          | the date bookmarked, exact for every bookmark; `published` when missing                                                                                                                                      |
| `media`              | derived | the media on the page, the quoted tweet's included         | `video` (any video or GIF), `photo` (1 image), `carousel` (2+ images) or `text` (none); a text-only bookmark quoting an image is `photo`                                                                     |
| `files`              | derived | the media on the page                                      | how many media files                                                                                                                                                                                         |
| `people`             | tagged  | the tags' `people`, plus each creator role that's a person | `[[links]]`: people, characters or groups. The creator roles are the bookmark's author, the quoted author and the reused media's first poster; your own account never counts.                                |
| `subjects`           | tagged  | the tags                                                   | `[[links]]`: concrete topics, things, works, products, places                                                                                                                                                |
| `themes`             | tagged  | the tags                                                   | `[[links]]`: broader ideas or genres                                                                                                                                                                         |
| `hashtags`           | native  | `hashtags`                                                 | the tweet's hashtags, without `#`                                                                                                                                                                            |
| `domain`             | tagged  | the tags                                                   | `[[links]]` to existing `Domains/` hubs, or empty                                                                                                                                                            |
| `description`        | tagged  | the tags                                                   | one plain sentence on what the bookmark is, from its text, free of contact details; empty when the text gives nothing                                                                                        |
| `online`             | tool    | —                                                          | `true` when written; `false` once the tweet is gone, set by hand (README, "Retry failures", says when)                                                                                                       |
| `thumbnail`          | tool    | the first media file on the page                           | `file:///` link to `thumbs\<tweet_id>.jpg` (how it's made: Design.md, "The pages"), so a text-only bookmark quoting an image gets that image as its cover; empty when there's no media or none could be made |
| `created`            | tool    | —                                                          | the day `build` wrote the page                                                                                                                                                                               |
| `tags`               | tool    | —                                                          | `[source, x]`                                                                                                                                                                                                |
| `created_by`         | tool    | —                                                          | `claude`                                                                                                                                                                                                     |

- **The page name** is the tagged `title` plus ` (<author>)`. The rules are in [Design.md](../../Design.md#the-pages), "The pages".
 
