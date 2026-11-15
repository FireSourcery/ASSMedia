
# ASSMedia: design

What ASSMedia does and why, how its folders are laid out, and what a page holds. 

ASSMedia turns the posts you save on social media into pages in an Obsidian vault: X bookmarks and Instagram saves so far, one platform at a time, each through gallery-dl and your own browser login.  

## Intent

I save posts I want back, and the platforms are bad at giving them back. I have 1000s of bookmarked posts across various social media platforms.
- **X bookmarks:** I search X by keywords, and sometimes I find one, sometimes I don't. They're a mix of text tweets and long posts, graphics such as character design sheets, videos, and replies, threads and quote tweets.
- **Instagram saves:** when I half-remember one, it's usually by **what was in it**, a person, a subject or a theme, more than by who posted it.

Once I find one, I want to:
- **share it:** send the link, or the local file if the post has been deleted
- **link to it** from my own notes in the vault
- **rewatch it**
- **cite it** as evidence on a wiki concept page

So each saved post becomes one page in the vault's wiki, recording what it's about, so I can find it by person, subject, theme, creator or any word of its text. Shared people, subject and theme pages tie posts from every platform together, and an Obsidian Base per platform serves as the index.

## Goals

1. **Every post has a page:** every saved post that's downloaded has a page in the vault. Searching any word of its text finds it: an X tweet, its thread or the tweet it quotes, or an Instagram caption.
2. **Shared pages:** entity and concept pages are shared across platforms, so "everything about this person" shows posts from all of them.
3. **Media on the page:** from a post's page I can play its videos, see its images inline, and copy its link.
4. **Two steps:** new posts are added with one update command per platform (mine) and a processing pass (Claude's).
5. **The vault's rules:** all of this follows the vault's own rules, in its `CLAUDE.md`.
6. **Anyone's setup:** anyone can run the tool on their own setup. Every path, account and program comes from one config file, `assmedia.toml`, and none is written in the code.

## Non-goals

- **Transcription:** no OCR, speech-to-text or image analysis. What a post is about comes only from text: its caption or tweet, a thread, a quoted tweet, an X Article, hashtags and the creator. A post with no text goes to "Needs tags", and I fill it in by hand.
- **Media inside the vault, phone sync:** videos and images stay under `<raw>`. Moving them later only changes the pages' media links, which `assmedia.py relink` rewrites.
- **Routine "is it still online" checks:** see `online` in the schemas.
- **New page properties:** each platform's `Schema.md` records the mapping as it is. Extra properties are a later decision.
- **Linked web pages:** links in posts stay links. They aren't fetched.
- **Edits on the platform:** once a post's page is written, later edits aren't picked up.

### X

- **Likes:** only Bookmarks.
- **Bookmark folders:** X Premium folders aren't recorded. gallery-dl reads only the main Bookmarks list.
- **Other people's replies:** a thread means the chain above the bookmarked tweet plus the author's own continuation, never the reply section.

### Instagram

- **Instagram collections:** which saved collection a post belongs to isn't recorded.

## Anti-goals (failure even if it technically works)

- **Invented tags:** a `people`, `subjects` or `themes` entry the post's text doesn't support. If the text names nothing, the fields stay empty.
- **A cluttered wiki:** hundreds of concept pages that each link to a single post.
- **Edits to the raw:** gallery-dl's JSON and media under `<raw>` are never edited.
- **Instance data in git:** the repo tracks the tool, its tests and docs, and an example config, never `<raw>`, `<state>`, `logs\` or `assmedia.toml`. A vault kept in git holds no media either.
- **A flagged account:** every request goes through gallery-dl with its default pacing, and only I run commands that use my browser login. Claude never does.
- **Contact details gathered into the wiki:** a post's own text keeps any it has, word for word, on its own page. They do not go into the Vault's `People\`.
- **Renamed pages:** a page name stays as true to its text as possible. Only characters that file names can't hold are changed, and pages aren't renamed afterwards.

### X

- **Downloading other people's media in bulk:** thread lookups download media only from the bookmarked tweet's author. Everyone else's tweets in a thread are kept as text.
- **Losing the record of finished lookups:** a lookup counts as done only when gallery-dl has commented out its URL in a `<state>\X\_crawl\threads-*.txt` list. If those lists were lost, every lookup would be queued again.

## How it works

1. **Update (you):** one command per platform downloads new posts and reports what's waiting. For X, it also queues and runs the thread lookups. On a new instance, `update --full` downloads everything.
2. **Process (Claude):** in batches of up to about 150:
   - tag each post from its text (for X, a mechanical pass first settles what has an exact answer)
   - write its page and thumbnail
   - create the entity and concept pages that enough posts link to, with their index lines
   - add one line to `wiki/log.md`
3. **Retry (you):** failed downloads and lookups are retried by hand from their failure lists.

**Reading the files:** each command lists the downloads once and reads each JSON file once. Bulk reads of JSON files and vault pages run 16 at a time (`assmedia\core\fsread.py`). On a NAS each file open costs a round trip whatever its size, so that's where the time goes.

## Tool layout

```
<project>\                        the tool: one git repo
  README.md  Design.md  Tagging.md     how to run it, this document, the tagging rules
  assmedia.example.toml              the config's template; copied to assmedia.toml and filled in
  assmedia.toml                      your instance config (not tracked)
  assmedia.py                        the entry point
  assmedia\                          the package
    core\                              what every platform shares (below)
    x\                                 X's code, gallery-dl configs and Schema.md
    instagram\                         Instagram's code, gallery-dl config and Schema.md
  tests\                               core\, x\, instagram\, and instance\ for your own config
  logs\                                finished records (not tracked)

<state>\                          what the tool keeps for itself ([paths] state; not tracked)
  X\  _crawl\  tagging\  build\
  Instagram\  _crawl\  tagging\  build\
```
 
- **Login:** the browser in `[gallery-dl] cookies`.
- **Download record, log and failures:** under `<state>\<Platform>\_crawl\`.
- **Output:** `<raw>\<Platform>\items\<id>\<id>_NN.<ext>`, plus the post's JSON from the metadata post-processor (event `post`, `skip: true`).
- **What the tool pulls,** under `<raw>`, is laid out in the README's [On your disk](README.md#on-your-disk).
- **`raw` and `state` can be anywhere:** they're paths in the config. They may sit inside the project, as `raw\` and `state\`, which `.gitignore` covers.

- **`assmedia\core\`:**
  - collections and paths
  - concepts: the entity and concept pages, and `vocab`
  - tags and frontmatter
  - text escaping and contact detection
  - titles and the emoji names table
  - thumbnails
  - the parallel reader
  - the filled-in gallery-dl configs
  - `relink`
  - the config loader

A platform's code imports the core, never another platform's code.
- **`_crawl\`:** gallery-dl's download record (`gallery-dl-archive.sqlite3`, what keeps updates incremental: if it's lost, the next update downloads everything again), its log and failure list, and the filled-in `gallery-dl.conf`. 
- **`tagging\` and `build\`:**
  - **`tagging\`** holds what later batches keep using: each platform's `creator-people.json` (username to person) and X's `declined-names.json`.
  - **`build\`** holds what one batch writes and reads. Nothing reads it after that batch's `build` and `concepts-apply`, so it's safe to delete, and a later fix goes on the page, not into a build file.
- **`logs\`:** finished documents kept as records. They keep what was true when they were written, old paths included.

### Output
```
<raw>\                            what the tool pulls ([paths] raw; not tracked)
  X\  items\<tweet_id>\  threads\  thumbs\<tweet_id>.jpg
  Instagram\  items\<shortcode>\  thumbs\<shortcode>.jpg
```
- **`items\` and `thumbs\` are linked from the pages,** as `file:///` URIs. If they move, `assmedia.py relink` rewrites the links. No command rebuilds thumbnails.

### Tool and instance

The tool holds only general behavior. Everything about one setup comes from the instance config, `assmedia.toml`:
- the `raw` and `state` folders, the vault, and ffmpeg
- the browser gallery-dl reads the login from
- one section per platform: your own X accounts, and the account whose Instagram Saved feed `update` reads

A platform with no section isn't set up. Its commands say so, and the other platform's still work.

The tool reads `assmedia.toml` beside `assmedia.py`, or the file `--config <path>` names. Its keys and how to fill them in are in the README's [Setup](README.md#setup). Data the tool makes goes under `raw` and `state`, never beside the code.

**The gallery-dl configs hold only behavior:** the per-subcategory blocks, filters, file names and post-processors. Before each run, the tool fills in the paths and the browser from `assmedia.toml` and writes the result to `<state>\<Platform>\_crawl\gallery-dl.conf`, which gallery-dl runs with.

**Every platform is known to every command:** the collections are built from the one config. So X's commands see Instagram's captions and creator map, and Instagram's see X's.

### What git tracks

| Tracked | Not tracked (`.gitignore`) |
|---|---|
| `assmedia\`, `tests\`, `assmedia.py` | `raw\`, `state\`, `logs\` |
| the docs and `assmedia.example.toml` | `assmedia.toml` |
| `.gitignore` | `__pycache__\`, `.superpowers\` |

So the pulled data, the download records and the creator maps have no git history. Until they move somewhere tracked privately, the disk is their only copy. A test fails if the repo ever tracks one of them.

## Media downloads

### X

- **`items\`:** three kinds of folder.
  - **A bookmark:** a folder holding `<tweet_id>.json`.
  - **A quoted tweet:** one holding only `<tweet_id>.quoted.json`, saved because a bookmark quotes it.
  - **A thread tweet:** one holding only media, by the bookmark's author. Its JSON is in `threads\`.

### Instagram

- **`items\`:** a folder holding `<shortcode>.json` and its media, numbered `<shortcode>_01` and up, is a complete post. A folder with a `.part` file, a gap in the numbering, or fewer files than gallery-dl's `count` is incomplete and waits.
Each platform has one gallery-dl config, in its package folder. The README, "Update", has how each update stops and what it prints.
 

## The pages

| What | Where | Notes |
|---|---|---|
| One page per post, with its text | `wiki/sources/X/<title>.md`, `wiki/sources/Instagram/<title>.md` | collection folders; a page stays there whatever its domain; written once |
| Entities and concepts | shared: `wiki/entities/`, `wiki/concepts/`, or the folders of the page's first domain | see "Tags, entities, concepts, domains" |
| The indexes | `Bases/X Bookmarks.base`, `Bases/Instagram Saves.base` | see "The Bases" |

Every page has the same shape:
1. the title
2. the media, inline: each video an inline `<video>` player, each image an inline `file:///` image
3. the text, word for word, in quote blocks, escaped so it shows exactly as written

The escaping backslashes Markdown characters (`#`, `*`, `_`, `>`, `[`, `]`, `|`, backticks), so hashtags don't become live Obsidian tags. Carriage returns are line breaks. Contact details stay as written: they're allowed in the wiki for now. Their organized home is `People/`, and whether wiki copies move there is open.

The page is the raw copy: `<raw>` holds the JSON and media, and the vault holds no other copy.

- **Properties:** defined in each platform's `Schema.md`, with the native field each comes from.
- **Thumbnail:** the `thumbnail` property, which feeds the Gallery cards. It's `<raw>\<Platform>\thumbs\<id>.jpg`: a frame grabbed with ffmpeg for a video, or a scaled copy of the first image.
- **Title:** always `<title> (<author>)`, then ` - <id>` if that name is taken anywhere in the vault. The page written first keeps the plain name.
  - **The tagger's title** is in English, translating other languages, as [Tagging.md](Tagging.md) sets out.
  - **True to the text:** a page name keeps the text's own words and capitals. Only characters that file names can't hold are changed, so `What did I just watch?!` names a page `What did I just watch ! (<author>)`.
  - **The id** is a property, not an alias.
- **When it's written:** once, by `build`. Pages already written are skipped, so hand edits survive.

### X: `wiki/sources/X/<title>.md`

- **The media** comes from the author's own tweets, in thread order:
  - their earlier tweets above the bookmark, if any
  - the bookmarked tweet
  - their continuation below it
  - then the quoted tweet's media

  Videos have no fixed width, so Obsidian shows each at its own size, up to the pane's width. Other people's tweets in the thread contribute text only.
- **The text:** each tweet is its own quote block, with its author, date and X link. The sections come in this order:
  1. `## Earlier in the thread`: each tweet above the bookmarked one, or `*(earlier tweets unavailable)*` when the chain breaks
  2. `## Bookmarked tweet`
  3. `## Continuation`: the author's own tweets below it
  4. `## Quoted tweet`: with the full text of an X Article if there is one, or `*(quoted tweet unavailable)*` and its link

  An empty text is `*(no text)*`.
- **When it's written:** only once the bookmark's thread lookup has finished. If the lookup fails for good (the tweet was deleted, say), its id goes in the skip list, and the page is written from the bookmark's own JSON. After a rate-limit or login failure, the bookmark stays pending until a retry.
- **The title's backstop,** when the tags have no title (no text at all, or a tagging slip, which `build` reports): the first line of the article title or text, then the quoted tweet's.
  - Links, leading @mentions and hashtags are dropped. A line of hashtags alone keeps their words.
  - A line with contact details is never used.
  - With no text at all, the title is the media kind: `Video`, `Photo`, `Images` or `Tweet`.
- **Which tweets get pages:** only bookmarks. A tweet fetched only because a bookmark quotes it, or only because it's in a thread, gets no page of its own. Its text is on the bookmark's page.
  - **Telling them apart:** by file name (see "Where things live"). Quoted tweets also carry `date_bookmarked`, inherited from the bookmark that quotes them, so that field can't be the test.
  - **Bookmarks that are also quoted** by another bookmark are bookmarks: they have their own `<tweet_id>.json`.

### Instagram: `wiki/sources/Instagram/<title>.md`

- **The media,** in post order. Each video is a `<video controls preload="metadata" width="360">` player: Markdown embeds of files outside the vault don't play, and Instagram videos are mostly vertical, so the width is fixed.
- **The caption:** in one quote block. An empty caption is `*(no caption)*`.
- **Saved date:** the day the post's folder was made, which is the download day. Instagram's feed carries no saved date, so a first full download dates the whole backlog that day, and the All view then orders it by `published`. `saved` is defined in [Schema.md](assmedia/instagram/Schema.md).
- **When it's written:** when the post's folder is complete.
- **The title's backstop,** when the tags have no title: the caption's first line with words.
  - Links, leading @mentions, hashtags, emoji and other symbols are dropped. A line of hashtags alone keeps their words.
  - `$` is dropped, and a line with contact details is skipped.
  - **No words:** the names of the caption's emoji, as CLDR short names, each once, in order, comma-separated, in sentence case. Skin tones and variation selectors are ignored, and a flag becomes `<country> flag`. The names come from `assmedia\core\emoji_names.json`, because the tool runs with `py -I` and can't import the `emoji` package. `assmedia\core\make_emoji_names.py` rebuilds the table.
  - **No words and no emoji:** the media kind, `Video`, `Photo` or `Images`.
  - So a caption of only 🌸💞 names a page `Cherry blossom, revolving hearts (<username>)`, and a photo with no caption, whose plain name is taken, `Photo (<username>) - <shortcode>`.

## Tags, entities, concepts, domains

The rules for tagging a post are in [Tagging.md](Tagging.md). In short:
- **What they mean:** `people` are named people, characters or groups who appear or are featured. `subjects` are concrete topics, things, works, products and places. `themes` are broader ideas or genres.
- **Where they come from:** only the post's text, hashtags, and the creator's username and display name. Never an author's bio.
- **Creators as people:** when the account is an individual person, the creator goes into `people`, by display name, and their page gets the username as an alias. Brands, shops, media outlets, fan pages and repost accounts don't count. When it's unclear, the creator is left out. The mapping is kept in each platform's `tagging\creator-people.json`, so a username always maps to the same name.
- **Empty texts:** if the text supports nothing, `subjects`, `themes` and `description` stay empty, and the post appears in the "Needs tags" view for me to fill in by hand.

**Shared pages:** one set of entity and concept pages for every platform.
- **The threshold:** a name gets a page once 2 or more posts link to it, every platform counted together. With fewer, the link stays unresolved.
- **Kinds:**
  - `person`
  - `organization`: brands, shops, studios
  - `product`: products and works
  - `channel`: accounts, blogs, shows
  - `tool`: software
  - `concept`: ideas, topics, genres

  Names from `people` default to `person`, and names from `themes` to `concept`.
- **Entity and concept pages** are written by `concepts-apply`, all in one shape. For a creator who counts as a person, `url` is their profile on the platform whose creator map names them, unless the page already has a URL.
- **What each page gets:**
  - `domain`: the union of the linking pages' domains, unless Claude sets it
  - an "In one sentence" line, backed only by the linking posts' text
  - an embedded Base view per collection: `## Instagram saves`, then `## X bookmarks` under it
- **Evidence:** the embedded view is the complete, live list. `## Sources` lists only the posts whose text backs up the page's own text, quoting them.
- **Existing pages:** pages in `wiki/entities/`, `wiki/concepts/`, the domain folders or `People/` are matched by name or alias and reused, never duplicated. An existing wiki page gets any missing embedded view appended, and its creators' usernames from every platform as aliases. `People/` notes are never edited.
- **Placement:** where the vault's `CLAUDE.md` puts pages. A page whose first domain has a domain folder goes in `<Domain>/wiki/entities/` or `<Domain>/wiki/concepts/`, with its index line in `<Domain>/wiki/<Domain> index.md`. Otherwise it goes in the shared `wiki/entities/` or `wiki/concepts/`, with its line in `wiki/index.md`.
- **Domains:** only existing hubs in `Domains/`, otherwise `[]`. New domains are proposed, never created.

### X

- **Text used:** the tweet, its thread, the quoted tweet and the article, plus hashtags, and the authors' usernames and display names. A @mention is a name in the text, tagged only when the tweet is about that account.
- **Three creators per bookmark,** each going into `people` when the account is a person:
  1. the bookmark's own author
  2. the quoted tweet's author
  3. the account that first posted media the bookmark reuses (gallery-dl's `source_user`, shown by X as "From @…")

  So for art reposted or quoted by someone else, the artist gets tagged. `source_author` and the "By creator" view stay the bookmark's own author. My own accounts (`[x] own`) never get a creator person.
- **The mechanical pass:** `export` decides first what needs no judgment, so tagging is spent on what does (`assmedia\x\prefill.py`, rules in [Tagging.md](Tagging.md)).
  - **What it settles:** creator roles with no account behind them, my own accounts, usernames already mapped, accounts whose earlier bookmarks never got a person (Claude may still set one), and every text field of a bookmark with no words to tag.
  - **What it suggests:** known names the bookmark's own text writes out, in their existing spelling. A name needs two words, or one capitalized word for a person, because one-word subjects and themes are mostly ordinary words. Suggestions are leads, never tags.
  - **Its memory:** the vault's source pages and the creator maps, never an earlier batch's build files, so `build\` stays safe to delete.
  - **What it doesn't check:** whether a tag's name appears in the text. Most tags that don't, such as full names, disambiguated titles and themes, are right.
- **Declined names:** some names reach the threshold and get no page by choice. `<state>\X\tagging\declined-names.json` records each one with its link count and batch, so they don't come back in every later batch, and no old batch file is needed to know them.
  - **Recording:** `concepts-apply` adds every name in its batch's plan that the concepts file leaves out.
  - **Filtering:** `concepts-plan` lists a declined name apart from the new ones, unless its link count has grown since. Then it's offered again.

### Instagram

- **Text used:** the caption and hashtags, plus the creator's username and display name.

## The Bases

Each platform's Base is filtered to its collection folder, with the same views:
- **Gallery:** cards with the thumbnail, title, `source_author` and `description`. Only pages with no media at all show a card without a cover.
- **All:** title, `source_author`, `published`, `media`, `people`, `subjects`, `themes`, `online`.
- **Needs tags:** pages with an empty `description`, whether or not `people` holds the creator.
- **Offline:** `online` is false.
- **By creator:** grouped by `source_author`.

The tool doesn't write the Base files: each is made once, by hand, with these views. `wiki/index.md` has one Sources line per collection, linking to its Base, instead of a line per page. `wiki/log.md` gets one line per processing pass.

**What the vault's rules need to allow,** where they'd say otherwise:
- **The index:** that one line per collection.
- **Source pages:** every saved post gets a source page from its text, even one whose text is only a short caption.

### X: `Bases/X Bookmarks.base`

Filtered to `wiki/sources/X/`. Its index line is `[[X Bookmarks.base|X bookmarks]]`.

### Instagram: `Bases/Instagram Saves.base`

Filtered to `wiki/sources/Instagram/`.

## Config
### X

**One config, two setups.** `assmedia\x\gallery-dl.conf` holds both. gallery-dl reads settings per extractor, so the Bookmarks feed takes the `twitter.bookmark` block and a single-tweet lookup takes the `twitter.tweet` block. Settings shared by both sit at the `twitter` level. Post-processors sit only in the blocks, because gallery-dl adds them up from every level.

**The bookmarks pass** (the `bookmark` block):
- **Output:** `<tweet_id>.json` for a bookmark, and `<tweet_id>.quoted.json` for a tweet it quotes.
- **X settings:**
  - `text-tweets: true`, or text-only bookmarks are skipped.
  - `quoted: true`, so quoted tweets and their media come along.
  - `unique: false`, so a tweet saved first as a quote still gets its own `<tweet_id>.json` when it comes up as a bookmark.
- **Quality:** gallery-dl's defaults, which are original-size images and the best video variant. Detailed images such as character sheets are worth keeping at full resolution. If video size becomes a problem, revisit it.
- **A known warning:** "Error while processing article data (KeyError: 'media_entities')" appears on every X Article read from the feed. The tweet and the article's cover are still saved, and the rest comes with the article's lookup.

**Thread lookups** (the `tweet` block): one lookup per bookmark that needs it, run from a URL list with `-I`, with their own log and failure list.
- **Who needs one:** a bookmark that's a reply or has a thread, and every X Article, bookmarked or quoted. The Bookmarks feed carries only an article's title and cover. The lookup carries its text and the images inside it.
- **What it returns:** the tweets above the bookmarked one, back to the first, and the author's own continuation below it.
- **When it stops:** at the first reply by someone else, so it never pages through a reply section. Popular tweets have thousands of replies. Each URL in the list comes after its own `-post-filter` and `-file-filter` lines, keyed to the author's numeric id.
- **Media:** only for tweets by the bookmarked tweet's author. In single-tweet mode with `conversations`, gallery-dl's `user` is the focal tweet's author, so the file filter is `author['id'] == user['id']`. Everyone else's tweets are JSON only, in `<raw>\X\threads\`.
- **Article text** comes from X's raw article blocks in the lookup's JSON, not from gallery-dl's HTML, so code blocks and embedded tweet links are kept.
- **Pacing:** X rate-limits lookups, and gallery-dl waits on its own. `-I` comments out each line once it's done, so a run can be stopped and resumed.

**Why lookups are a second pass:** gallery-dl's `expand` option would fetch threads in the bookmarks pass itself. But it gives every bookmark a wrong bookmark date, pages through whole reply sections, downloads other people's media with no way to limit it, and spends a request on every bookmark, not just the ones that need a lookup. So the update runs the two passes with `pending` between them, which picks the bookmarks that need a lookup.

### Instagram

`assmedia\instagram\gallery-dl.conf`, read by `update`:
- **Videos:** `"videos": "merged"`, Instagram's 720p file, so neither yt-dlp nor ffmpeg is needed to download.
- **Media type and file count** come from the downloaded files, not from gallery-dl's labels ([Schema.md](assmedia/instagram/Schema.md)).

## Other cases

- **Unsaving:** removing a post from Bookmarks or Saved doesn't remove its page. Pages are deleted only by hand.
- **A deleted post:** when a download error says a post no longer exists and it has a page, that page's `online` is set to `false` by hand. Rate-limit and login errors never count. The README, "Retry failures", has the steps.
- **Older Instagram page layouts:** `update-media` brings a page written by an earlier version of the tool to the current body, and skips any page with other text between its title and caption.

## Known gaps

- **Some features are X-only:** declined names and the mechanical pass. Instagram could use both ("Later", item 3).
- **Each step reads its pages again:** `export` reads some page sets twice, and `concepts-plan` builds its page index three times. In parallel each pass costs a second or two. Sharing the reads between steps is the speed-up left.
- **No history for the instance data:** the pulled data and `state` aren't in git (see "What git tracks").

## Later

1. **The data into the vault:** `raw` (or just its thumbnails) could move into the vault, with vault-relative links that work on other machines and a phone. It's a config change plus a relink, and the vault's git would need to ignore the media.
2. **Publishing:** on GitHub.
3. **One processing path for every platform:** the tool may be unified further, so that platforms differ in three things only:
   - **What's pulled:** which posts and which of their data, through the platform's gallery-dl config.
   - **Its native schema:** the fields the platform has and gallery-dl gives, recorded in its `Schema.md`.
   - **Its mapping:** how those fields fill one shared page schema in Obsidian, a properties template that every platform's pages follow.

   Post-processing would then be one code path for all of them: `vocab`, `export`, tagging, `build` and the concepts steps. The mechanical pass and declined names, X-only now, would come to every platform with it. As a first step, the two `Schema.md` property tables share one shape (Property, Origin, From, Notes): the properties and their order already match apart from the post's id, and From is where the platforms differ.
4. **More platforms:** each is a package beside `x\` and `instagram\`, with its own gallery-dl config and `Schema.md`. After item 3, those and its mapping are all a new platform needs.
5. **A Social Media domain**, possibly with its own domain folder, is considered then.

## Docs and history

Each piece of the docs lives in one place, and the others link to it:

| Doc | Holds |
|---|---|
| [README.md](README.md) | what you get (the files on disk and the pages in the vault), commands, setup and run notes |
| `Design.md` | what the tool does and why, the folder layout, what a page holds |
| [X's](assmedia/x/Schema.md) and [Instagram's](assmedia/instagram/Schema.md) `Schema.md` | gallery-dl's native fields and the page properties |
| [Tagging.md](Tagging.md) | tagging rules |
| `logs\` | finished records, kept as written and not tracked |

**How a revision works:** it's drafted at the root as `Revision N.md`, with its plan as `Revision N Plan.md`. When it's done, what lasts goes into this design and the README, and both files move to `logs\` as `.log.md`.
