# Instagram saves: schema

What gallery-dl 1.32.19 gives for each saved post, and where each field ends up on a save page. This is the one place the page properties are defined. 

**Where a field can go:**
- **property:** a page property, by name
- **body:** a part of the page body
- **tool:** used by the tool but not written to the page
- **raw only:** kept in the JSON and nowhere else

gallery-dl's metadata post-processor runs once per post (event `post`), so per-file fields such as a file's size or a video's length aren't saved.

## Native fields: the post

| Field                                                                             | Type                        | Meaning                                                | Goes to                                                                                      |
| --------------------------------------------------------------------------------- | --------------------------- | ------------------------------------------------------ | -------------------------------------------------------------------------------------------- |
| `post_shortcode`                                                                  | text                        | the post's short id, as in its URL                     | property `shortcode`; the folder and file names                                              |
| `post_url`                                                                        | text                        | the post's link                                        | property `source_url` (built from the shortcode when missing)                                |
| `post_id`, `owner_id`                                                             | text                        | numeric ids of the post and its account                | raw only                                                                                     |
| `username`                                                                        | text                        | the account that posted it                             | property `source_author`; the page name's ` (<username>)`; the creator map's key             |
| `fullname`                                                                        | text                        | that account's display name                            | property `source_author_name`; used for `creator_person`                                     |
| `post_date`                                                                       | text, `YYYY-MM-DD hh:mm:ss` | when it was posted                                     | property `published` (the date part); a post without a readable date is incomplete           |
| `date`                                                                            | text                        | the same as `post_date`                                | raw only                                                                                     |
| `description`                                                                     | text                        | the caption                                            | body, as a quote block; the title backstop; tagging                                          |
| `tags`                                                                            | list of text                | the caption's hashtags, with `#`                       | property `hashtags`, without `#`; tagging                                                    |
| `count`                                                                           | number                      | gallery-dl's file count, including a reel's soundtrack | tool: how many media files a complete post needs                                             |
| `audio_artist`, `audio_title`, `audio_duration`, `audio_timestamps`, `audio_user` | mixed                       | the reel's soundtrack                                  | tool: their presence means `count` includes a file that isn't downloaded; otherwise raw only |
| `sidecar_media_id`, `sidecar_shortcode`                                           | text                        | ids of an item inside a carousel post                  | raw only                                                                                     |
| `coauthors`                                                                       | list of accounts            | collaborators on the post                              | raw only                                                                                     |
| `location_id`, `location_name`, `location_slug`, `location_url`                   | text                        | a tagged place                                         | raw only                                                                                     |
| `likes`                                                                           | number                      | likes when downloaded                                  | raw only                                                                                     |
| `liked`                                                                           | true/false                  | whether you liked it                                   | raw only                                                                                     |
| `pinned`                                                                          | list                        | gallery-dl's pinned list for the post                  | raw only                                                                                     |
| `type`, `subcategory`, `category`                                                 | text                        | gallery-dl's own labels (`post`, `instagram`)          | raw only: media type comes from the files instead                                            |
| `subscription`                                                                    | empty                       | present but empty                                      | raw only                                                                                     |

**From the files, not the JSON:** `media` and `files` come from the downloaded files (below).

## Obsidian page properties

The properties `render_page` writes (`assmedia/instagram/page.py`), in this order. X's [Schema.md](../x/Schema.md#obsidian-page-properties) has the same table: the same properties in the same order, apart from the post's id.

**Origin:** `native` is a gallery-dl field, named under From. `derived` is worked out from fields or the downloaded files. `tagged` comes from Claude's tags file, under the rules in [Tagging.md](../../Tagging.md). `tool` is set by the tool itself.

| Property             | Origin  | From                                                    | Notes                                                                                                                   |
| -------------------- | ------- | ------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `type`               | tool    | —                                                       | always `source`                                                                                                         |
| `source`             | tool    | —                                                       | always `Instagram`                                                                                                      |
| `shortcode`          | native  | `post_shortcode`                                        | the post's id, as in its link; in place of X's `tweet_id`                                                               |
| `source_url`         | native  | `post_url`                                              | the Instagram link, built from the shortcode when missing                                                               |
| `source_author`      | native  | `username`                                              | the username, plain text; the "By creator" view groups on it                                                            |
| `source_author_name` | native  | `fullname`                                              | the display name, as Instagram shows it                                                                                 |
| `published`          | native  | `post_date`                                             | the date posted, date only                                                                                              |
| `saved`              | derived | the post's folder                                       | the day the folder was made (the download day), because Instagram's feed has no saved date                              |
| `media`              | derived | the downloaded files                                    | `carousel` (2+ files, videos included), `video` (one `.mp4`) or `photo` (one image)                                     |
| `files`              | derived | the downloaded files                                    | how many media files                                                                                                    |
| `people`             | tagged  | the tags' `people`, plus `creator_person` when it's set | `[[links]]`: people, characters or groups, the creator included when the account is a person                            |
| `subjects`           | tagged  | the tags                                                | `[[links]]`: concrete topics, things, works, products, places                                                           |
| `themes`             | tagged  | the tags                                                | `[[links]]`: broader ideas or genres                                                                                    |
| `hashtags`           | native  | `tags`                                                  | the caption's hashtags, without `#`                                                                                     |
| `domain`             | tagged  | the tags                                                | `[[links]]` to existing `Domains/` hubs, or empty                                                                       |
| `description`        | tagged  | the tags                                                | one plain sentence on what the save is, from its caption, free of contact details; empty when the caption gives nothing |
| `online`             | tool    | —                                                       | `true` when written; `false` once the post is gone, set by hand (README, "Retry failures", says when)                   |
| `thumbnail`          | tool    | the first media file                                    | `file:///` link to `thumbs\<shortcode>.jpg` (how it's made: Design.md, "The pages"); empty when none could be made      |
| `created`            | tool    | —                                                       | the day `build` wrote the page                                                                                          |
| `tags`               | tool    | —                                                       | `[source, instagram]`                                                                                                   |
| `created_by`         | tool    | —                                                       | `claude`                                                                                                                |

- **The page name** is the tagged `title` plus ` (<username>)`. The rules are in [Design.md](../../Design.md#the-pages), "The pages".
