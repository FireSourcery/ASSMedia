# ASSMedia

**Anti-Social Social Media.** Your X bookmarks and Instagram saves, downloaded to your own disk and filed as pages in your Obsidian vault: the posts you kept, without the feed.

What the tool gives you, its commands, and how to run them live here. The other docs link to this file instead of repeating it.

- **What it does:** [the files on your disk and the pages in your vault](#what-it-does)
- **Schemas:** [X](assmedia/x/Schema.md) and [Instagram](assmedia/instagram/Schema.md): every page property and the gallery-dl field it comes from
- **Design:** [Design.md](Design.md): why it works this way, [the tool](Design.md#tool-layout), [its downloads](Design.md#media-downloads), and [what a page holds](Design.md#the-pages)
- **Tagging rules:** [Tagging.md](Tagging.md)
- **A new machine or another user:** [Setup](#setup)

Every command is `py -I <project>\assmedia.py <platform> <command>`, with `x` or `instagram` as the platform. `<project>` is this folder. `--config <path>` before the platform picks a config other than `assmedia.toml` beside `assmedia.py`. Below, `<raw>`, `<state>` and `<vault>` are the `[paths]` from that config, and `<Platform>` is `X` or `Instagram`.

## What it does

ASSMedia downloads the posts you've saved, X bookmarks and Instagram saves, into a folder you choose, and gives each post a page in your Obsidian vault. On that page you can play its videos, see its images, read its full text and open the original. Each page links the people, subjects and themes its text names, so you can find a post again by what was in it, not only by who posted it.

You run the downloads, with your own browser login ([Update](#1-update-you-run-this)). Claude reads each post's text, tags it and writes the pages ([Process](#2-process-claude-runs-these)).

### On your disk

The media and gallery-dl's JSON go under the folder you set as `[paths] raw` in `assmedia.toml`, one folder per platform:

```
<raw>\
  X\
    items\<tweet_id>\         one folder per tweet: <tweet_id>.json and its media, <tweet_id>_01.jpg, <tweet_id>_02.mp4 ...
    threads\                  the JSON of the tweets around a bookmark, from its thread lookup
    thumbs\<tweet_id>.jpg     each bookmark page's thumbnail
  Instagram\
    items\<shortcode>\        one folder per save: <shortcode>.json and its media, <shortcode>_01.jpg ...
    thumbs\<shortcode>.jpg    each save page's thumbnail
```

- **The media** is what the platform serves: X's original-size images and best video, and Instagram's 720p video.
- **The JSON** is all of gallery-dl's metadata for the post, kept whole, so a field that isn't on the page now can still be used later.
- **Nothing is edited or removed** once it's downloaded. Unsaving a post on the platform doesn't delete its files or its page.
- **What the tool keeps for itself,** its download records, logs, creator maps and batch files, goes under `[paths] state` ([Tool layout](Design.md#tool-layout)).

Neither folder is tracked by git.

### In your vault

Each post gets one page, in `<vault>\wiki\sources\X\` or `<vault>\wiki\sources\Instagram\`, named `<title> (<author>)`. From top to bottom, a page holds:
1. **Properties:** who posted it and when, when you saved it, its link, its media kind, the people, subjects and themes it's about as `[[links]]`, a one-sentence description, and a thumbnail for the gallery view.
2. **The media, inline:** each video as a player and each image in place, straight from `<raw>`.
3. **The text, word for word:** a bookmark's tweet with its thread and the tweet it quotes, or a save's caption.

**What each property holds, and the gallery-dl field it comes from,** is in each platform's schema: [X](assmedia/x/Schema.md) and [Instagram](assmedia/instagram/Schema.md). How titles are chosen, and how the text and media are laid out, is in [The pages](Design.md#the-pages).

**Around the pages:**
- **Shared pages:** a person, subject or theme that 2 or more posts link to can get a page of its own, shared by both platforms. It shows every post that links to it as a gallery of cards ([Tags, entities, concepts, domains](Design.md#tags-entities-concepts-domains)).
- **An index per platform:** an Obsidian Base, `Bases\X Bookmarks.base` or `Bases\Instagram Saves.base`. The tool doesn't create these two files; [The Bases](Design.md#the-bases) lists their views.
- **The vault's log and index:** each batch adds a line to `wiki\log.md`, and each new shared page gets a line in `wiki\index.md`, or in its domain folder's own index.

**Pages are written once.** Later edits on the platform aren't picked up, and a page that exists is skipped, so your own edits stay.

**Media links are `file:///` links** into `<raw>`, so the media plays on a computer that can reach that folder. If `<raw>` moves, rewrite the links. `--dry-run` only counts them:

```
py -I <project>\assmedia.py relink <vault>\wiki\sources <old raw> <new raw> [--dry-run]
```

## 1. Update (you run this)

You must be signed in to the platform in the browser named in `[gallery-dl] cookies`. Only you run `update`, because it uses that login.

Before it downloads, `update` writes the platform's gallery-dl config, with the paths and the browser filled in from `assmedia.toml`, to `<state>\<Platform>\_crawl\gallery-dl.conf`.

### X

```
py -I <project>\assmedia.py x update
```

It runs four steps in a row, and prints a line after each:
1. **Download new bookmarks** (gallery-dl, the config's `bookmark` block).
   - **How it stops:** gallery-dl reads Bookmarks newest first, and stops after 5 media files in a row that `<state>\X\_crawl\gallery-dl-archive.sqlite3` already has. Don't delete that file; it's what keeps updates incremental.
   - **Text-only bookmarks:** they have no files, so they never count toward the stop. They're picked up on the way.
   - **Rare early stop:** a run could stop early if 5 new bookmarks in a row all have media that was downloaded before, for example as a quoted tweet.
2. **Queue the thread lookups** (`pending`). Two kinds of tweet need a lookup, and their URLs are appended to `<state>\X\_crawl\threads-pending.txt`:
   - bookmarks that are replies, or that have replies
   - X Articles, bookmarked or quoted, because the Bookmarks feed carries only an article's title and cover. The lookup brings its text and the images inside it.

   Each URL comes after two option lines, keyed to the author's numeric id: `-post-filter` stops the lookup at the first reply by someone else, and `-file-filter` downloads only that author's media.
3. **Run the lookups** (gallery-dl, the config's `tweet` block). It's skipped when nothing is queued.
   - **What it saves:** JSON for every tweet in the thread goes to `<raw>\X\threads\`. Only the bookmark author's media is downloaded.
   - **Resuming:** `-I` comments out each stop line and URL once it's done, so the run can be stopped and resumed. X rate-limits these lookups, and gallery-dl waits on its own.
   - **Log and failures:** `<state>\X\_crawl\threads.log` and `threads-failed.txt`.
4. **Report:** `done: new N, ready N, still waiting N, failed lookups N`.

**Notes:**
- **When a lookup counts as done:** only once its own URL has run, meaning gallery-dl commented it out in some `threads-*.txt` list, and it isn't in `threads-failed.txt`. A thread file written by another bookmark's lookup doesn't count.
- **Claude doesn't run `pending` while `update` is running.** gallery-dl rewrites the list file after each lookup, and anything `pending` added in the meantime would be lost. The next `pending` adds it again.
- **Checking what's waiting:** Claude can run `assmedia.py x pending` at any time. It prints `new`, `ready`, `waiting_lookup`, `added_to_list` and `incomplete`, and queues any lookup that's missing.

**Failed lookups:**
- Read the reason in `<state>\X\_crawl\threads.log`.
- If the tweet was deleted or is protected, add its id to `<state>\X\_crawl\threads-skip.txt`, one per line. The bookmark is then built from its own JSON.
- If it was a rate-limit or login error, retry it. Rename the failed list first, because gallery-dl keeps its error file open and couldn't update a list it's also writing to. The `threads-retry-*.txt` name counts as a lookup list:

  ```
  Move-Item "<state>\X\_crawl\threads-failed.txt" "<state>\X\_crawl\threads-retry-1.txt"
  py -I <project>\assmedia.py x update --lookups "<state>\X\_crawl\threads-retry-1.txt"
  ```

  Use the next number for each later retry. New failures go to a fresh `threads-failed.txt`.

### Instagram

```
py -I <project>\assmedia.py instagram update
```

It runs two steps in a row, and prints a line after each:
1. **Download new saves** from the Saved feed of the account in `[instagram] saved`.
   - **How it stops:** gallery-dl reads Saved newest first, and stops after 5 media files in a row that `<state>\Instagram\_crawl\gallery-dl-archive.sqlite3` already has. Don't delete that file; it's what keeps updates incremental.
2. **Report:** `done: new N, incomplete N`, naming the incomplete folders. What makes a folder incomplete is in [Design.md](Design.md#media-downloads), "Media downloads"; the next update usually finishes it.

**Notes:**
- **Without `[instagram] saved`,** `update` refuses and says so.
- **Checking what's waiting:** Claude can run `assmedia.py instagram pending` at any time. It prints `N pending, N incomplete`.

### Both

- **The first full run:** `update --full` leaves out the stop after 5 known files.
- **Exit codes:** each gallery-dl pass prints its exit code. A non-zero code (one failed file is enough) doesn't stop the later steps or the summary.

## 2. Process (Claude runs these)

The same steps on both platforms, in batches of up to about 150:

```
py -I -X utf8 <project>\assmedia.py <platform> vocab
py -I <project>\assmedia.py <platform> export <name> --limit 150
```

- **`vocab`** prints the names already in use: wiki pages and their aliases, the names save and bookmark pages link to, the hubs, and the platform's creator map. It covers both platforms.
- **`export`** writes `<state>\<Platform>\build\export\<name>.json`, the next posts without a page.

Claude reads the export and writes `<state>\<Platform>\build\tags\<name>.json`, with the fields and rules in [Tagging.md](Tagging.md). Then:

```
py -I <project>\assmedia.py <platform> build <state>\<Platform>\build\tags\<name>.json
py -I <project>\assmedia.py <platform> concepts-plan <name>
```

**What `build` does:**
- writes each page once, and makes the thumbnails; pages that exist are skipped
- saves the creator mappings to `<state>\<Platform>\tagging\creator-people.json`; a username already mapped keeps its first name

**What `concepts-plan` writes** to `<state>\<Platform>\build\concepts\<name>.plan.json`. Instagram saves and X bookmarks count together:
- **`new`:** names linked often enough to get a page (the threshold is in Design.md, "Tags, entities, concepts, domains"), each with `fields`, `suggested_kind` and its linking pages. Each entry in `saves` has its `collection`, `Instagram` or `X`, its `description` and its `caption`.
- **`conflicts`:** names that clash with an existing vault note. Those get no page; retag the posts or tell the user.
- **`needs_embed`, `needs_embed_detail`:** existing pages that get `## Instagram saves` or `## X bookmarks` appended.

Claude writes `<state>\<Platform>\build\concepts\<name>.json`, as `{name: {...}}`. Each entry has:
- **`kind`:** `person` | `organization` | `tool` | `product` | `channel` | `concept`
- **`sentence`:** one line, no contact details
- **`aliases`:** optional
- **`domain`:** optional; the default is the union of the linking pages' domains
- **`url`:** optional; the default is the creator's profile, on the platform whose creator map names them
- **`sources`:** a list of page names, or `{"page", "quote"}` objects

Then:

```
py -I <project>\assmedia.py <platform> concepts-apply <state>\<Platform>\build\concepts\<name>.json
```

**What `concepts-apply` does:**
- creates the pages and their index lines
- appends the missing `## Instagram saves` or `## X bookmarks` lists to existing pages
- adds creators' usernames, from both platforms' creator maps, to the aliases of existing wiki pages; `People/` notes are never touched

**Finally,** add one line to `<vault>\wiki\log.md`:
`YYYY-MM-DD — added N X bookmarks (<name>) and M concept pages — [[X Bookmarks.base]], [[index]]`, or the same with `Instagram saves` and `[[Instagram Saves.base]]`.

**The files in `build\`** are used only within their batch. Nothing reads them afterwards, so the folder is safe to delete. A later fix goes on the page, not into a build file.

### X

- **`export` runs the mechanical pass first** ([Tagging.md](Tagging.md), "The mechanical pass"). It settles what has an exact answer: creators already mapped, accounts with no person in earlier bookmarks, a quote or reused media that isn't there, and bookmarks with no words to tag. It also suggests the known names each bookmark's text writes out.
  - **What it writes:** each bookmark in the export gets a `prefill` block, and `build\tags\<name>.json` is written as a starter with the settled fields filled in, unless that file exists already.
  - **What it prints:** `nothing to tag N, no words N, creators settled N, names suggested N`.

  Claude fills in the fields each bookmark's `prefill.to_tag` lists.
- **Three creator roles** in each tags entry: `creator_person`, `quoted_person` and `source_person`.
- **`build`** also reports `not_ready` for bookmarks still waiting for a thread lookup.
- **Declined names:**
  - **In the plan:** it has a **`declined`** list, the names an earlier batch chose not to give a page (`<state>\X\tagging\declined-names.json`). One comes back into `new` only when its link count has grown.
  - **On apply:** `concepts-apply` records every name in the plan's `new` list that the concepts file left out.
  - **Seeding:** `seed-declined` fills the file once from earlier batches. It refuses when the file exists.

### Instagram

- **`export`** puts the oldest downloads first.
- **Older page layouts:** `assmedia.py instagram update-media [--dry-run]` brings pages from earlier versions of the tool to the current body. It replaces only the tool's own lines between the title and the caption, and skips pages with other text there.
- **The emoji names table:** after upgrading the `emoji` package, rebuild `assmedia\core\emoji_names.json` with `py <project>\assmedia\core\make_emoji_names.py`. Use plain `py`, not `py -I`, so it can see the package.

## 3. Retry failures (you run this)

Rename the failed list first, because gallery-dl keeps its error file open and couldn't update a list it's also writing to. Use the next number for each later retry. New failures go to a fresh `failed-urls.txt`.

```
Move-Item "<state>\<Platform>\_crawl\failed-urls.txt" "<state>\<Platform>\_crawl\retry-urls-1.txt"
py -m gallery_dl -c "<state>\<Platform>\_crawl\gallery-dl.conf" -I "<state>\<Platform>\_crawl\retry-urls-1.txt"
```

The config here is the filled-in copy that the last `update` wrote.
- **When a post is gone:** if the error explicitly says a post no longer exists and it already has a page, set that page's `online` to `false` by hand.
- **Rate-limit and login errors** never count as gone.
- **Removing a post** from Bookmarks or Saved doesn't delete its page.

### X

The download pass's failure list only ever holds the Bookmarks URL, because gallery-dl records the URL it was given. So a retry re-reads the feed, without the stop after 5 known files.

**Listing another account's bookmarks** (metadata only, no media): `assmedia\x\gallery-dl-list.conf` holds that setup without its paths or browser.
1. Copy it, and add `base-directory` (for example `<raw>/X/_list/`), the twitter `cookies`, and `output.logfile.path`, as in the filled-in `gallery-dl.conf`.
2. Run `py -m gallery_dl -c <your copy> https://x.com/i/bookmarks`.

## Setup

Once per machine or user. Why the tool and the instance are kept apart is in [Design.md](Design.md#tool-and-instance).

1. **Install Python 3.11 or later** (3.14 is the tested version), **gallery-dl** (`py -m pip install gallery-dl`; 1.32.19 is the tested version) and **ffmpeg**, for video thumbnails. The tool itself uses only Python's standard library. It starts gallery-dl as a separate process, so gallery-dl can sit in your user site-packages.
2. **Copy `assmedia.example.toml` to `assmedia.toml`,** beside `assmedia.py`, and fill it in:
   - **`[paths]`, all required:**
     - `raw`: where pulled data goes, as `<raw>\<Platform>\items`, `threads` and `thumbs` ([On your disk](#on-your-disk))
     - `state`: where the tool keeps its records, as `<state>\<Platform>\_crawl`, `tagging` and `build`
     - `vault`: the Obsidian vault the pages go into
     - `ffmpeg`: the ffmpeg program

     Every path is absolute, written with forward slashes (`D:/Media/raw`). `raw` and `state` are made on the first run, while `vault` and `ffmpeg` must exist.
   - **`[gallery-dl] cookies`,** required: the browser you're signed in with (`firefox`, `chrome`, `edge` and so on).
   - **`[x]`,** one section per platform you use. Leave one out, and its commands say the platform isn't set up.
     - `own`: your own X usernames, without `@`, never tagged as a creator. It can be left out.
   - **`[instagram]`:**
     - `saved`: whose Saved feed `update` downloads. Without it, `update` refuses.
   - **Errors:** a missing key, a relative path, a missing vault or ffmpeg, or a platform with no section each stop the command with one `assmedia:` line naming the problem.
   - **Encoding:** the file is UTF-8. PowerShell 5's `>` writes UTF-16, which the tool names as the problem.
3. **First download:** `assmedia.py <platform> update --full`, then process in batches as in section 2, "Process".

## Tests

```
py -I -m unittest discover -s <project>\tests -t <project>
```

The tests use temporary folders. The ones in `tests\instance\` check your own `assmedia.toml` and files, for example that the filled-in gallery-dl configs write only under `raw` and `state`. They're skipped when there's no `assmedia.toml`, so a fresh clone passes.

## License

Public domain, under [the Unlicense](LICENSE). One file is the exception: `assmedia\core\emoji_names.json` lists emoji names from [Unicode CLDR](https://cldr.unicode.org/), by way of the `emoji` package, and those names stay under the [Unicode License](https://www.unicode.org/license.txt).
