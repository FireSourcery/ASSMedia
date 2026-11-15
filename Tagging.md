# Tagging rules

How the tagger, Claude, tags a batch of saved posts. The spec is [Design.md](Design.md), sections "The pages" and "Tags, entities, concepts, domains". The commands are in the [README](README.md), "Process". The rules are the same on every platform, and a `### X` or `### Instagram` part says where a platform differs.

## Input and output

Each batch is an export, `<state>\<Platform>\build\export\<name>.json`. The tagger writes `<state>\<Platform>\build\tags\<name>.json`: an object keyed by the post's id, with **exactly** the platform's fields for every post in the export, no more and no fewer.

**Names:** before tagging, run `vocab` and reuse its names. It covers every platform.

### X

- **Input:** a list of bookmarks. Each one has:
  - `tweet_id`, `author`, `author_name`, `text`, `hashtags`
  - `media` (`text`, `photo`, `carousel` or `video`)
  - `article_title`, `article_text`
  - `source_user`: the account that first posted reused media, or null
  - `above`: the tweets above it in the thread, each `{author, author_name, text}`
  - `below`: the author's continuation texts
  - `quoted`: `{author, author_name, text, article_title, article_text}` or null
  - `prefill`: what the mechanical pass settled and suggests (below)
- **Output:** `export` writes the tags file as a starter, with each bookmark's settled fields filled in, and the tagger fills in the rest:

  ```json
  "<tweet_id>": {"title": "", "description": "", "people": [], "subjects": [], "themes": [], "creator_person": null, "quoted_person": null, "source_person": null, "domain": []}
  ```

### Instagram

- **Input:** a list of `{shortcode, username, fullname, caption, hashtags, media}`.
- **Output:**

  ```json
  "<shortcode>": {"title": "", "description": "", "people": [], "subjects": [], "themes": [], "creator_person": null, "domain": []}
  ```

## The mechanical pass (X)

`export` settles what has an exact answer before you tag, and suggests names for the rest. Each bookmark's `prefill` block has:
- **`settled`:** fields already decided, each with its reason. The starter tags file holds their values.
  - **No such account, your own account, an existing creator mapping:** keep them. `build` enforces the last two anyway.
  - **An account whose earlier bookmarks never got a person:** keep `null`, unless this bookmark clearly shows an individual, such as a person's name as the display name. Earlier batches sometimes missed one, so set the name when the evidence is clear; `build` then maps it for good.
  - **No words to tag:** the text, thread, quote and article are empty, or only links and @mentions. `title`, `description`, `people`, `subjects`, `themes` and `domain` stay empty.
- **`to_tag`:** the fields left for you. A bookmark with an empty `to_tag` needs nothing.
- **`suggestions`:** names from earlier pages that this bookmark's own text writes out, by field and in their existing spelling. They're leads, not tags: tag one only when the bookmark is about it, by the rules below (@mentions, long posts). Names the text doesn't write out, such as a full name from a nickname, a series from an abbreviation and most themes, still come from `vocab`.

## Evidence

- **Allowed sources:** the post's own text, its hashtags, and the creators' usernames and display names. Nothing else counts: no outside knowledge of what an image or video shows, and no guessing.
- **Never used:** an author's bio, location or profile.
- **When the text gives nothing to tag** ("Check out my latest post", a bare emoji or reaction, an image with no text), leave `description`, `subjects` and `themes` empty. The post then lands in the user's "Needs tags" view. The creator fields may still be set.
  - **The title still gets written** whenever the text has words: an English rendering of them. Only an empty or emoji-only text leaves `title` empty too. `build` reports any post it had to name from raw text because the title was empty.

### X

- **The text** is the bookmarked tweet's `text`, the thread (`above`, `below`), the quoted tweet, and article titles and texts.
- **Images you can't read:** never tag a bookmark from an image. An image-only bookmark keeps `title`, `description`, `subjects` and `themes` empty.
- **@mentions:** a name in the text, tagged only when the tweet is about that account. Replies start with `@name @name` that the reply isn't about.
- **Long posts and articles:** tag what they're about, not every name they mention.

### Instagram

- **The text** is the caption.

## Fields

- **`title`:** a short readable title for the post, in sentence case, like "Night drive through Tokyo in the rain". Never include the creator; the tool adds it.
  - **Always in English,** because it becomes the file name. Translate text in another language.
  - No `$` (write "350 an hour", not "$350").
  - None of these characters: `\ / : * ? " < > | # ^ [ ]`.
- **`description`:** one plain sentence on what the post is, taken from its text. No `$` and no line breaks.
- **`people`:** named people, characters or groups who appear or are featured.
- **`subjects`:** concrete things such as works, products, companies, places and specific topics ("New York City", "Encryption").
  - Disambiguate songs and similar titles: "Bite Me (song)".
  - A brand or shop account is a subject only when the post is about the brand itself, never just because it posted.
- **`themes`:** broader ideas or genres. Reuse a theme the vault already has, from `vocab`'s `linked` names, whenever one fits. Only add a new theme when none fits. New themes are in sentence case ("Home decor").
- **`creator_person`:** the creator's name, only when the account is clearly an individual person.
  - Clean up the display name: drop emoji, taglines and decoration.
  - Never for brands, shops, media outlets, fan pages, meme or repost accounts, bands or topic channels.
  - When unsure, use `null`.
  - If `vocab`'s `creators` already maps this username, use exactly that name.
- **`domain`:** names of the vault's existing hubs only, as `vocab` lists them under `domains`. Use one only when the post clearly belongs to it, by what its hub note says the domain covers. A post that only mentions a domain's topic doesn't belong to it. Otherwise use `[]`.
  - Never use a hub's name as a theme or subject: a page with that name would clash with the hub.

### X: the three creator roles

Each role holds a person's name only when that account is clearly an individual person, by `creator_person`'s test above. Otherwise it's `null`.
- **`creator_person`:** the bookmark's own `author`.
- **`quoted_person`:** the `quoted` tweet's `author`. Leave it `null` when `quoted` is null.
- **`source_person`:** the `source_user`, the original poster of reused media such as an artist whose art someone else posted. Leave it `null` when `source_user` is null.
- **Your own account:** never gets a person in any role, and the build drops one if it's set.
- **Existing mappings:** if `vocab`'s `creators` already maps the username, use exactly that name.
- **Duplicates:** a person who's both in `people` and a creator role is fine, because the page lists them once.

## Names

- **Reuse existing names.** `vocab` lists existing pages (`pages`, with aliases), names already used (`linked`) and creator mappings (`creators`). Reuse those exact spellings. If a name matches an alias, use the page name instead.
- **Banned characters:** none of `\ / : * ? " < > | # ^ [ ]` in any name, and no leading `.`.
- **One name per thing,** throughout the batch: always "Final Fantasy VII", never also "FFVII".
