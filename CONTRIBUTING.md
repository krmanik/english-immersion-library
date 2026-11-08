# Contributing to English Immersion Library

Thanks for helping other learners find good English content. Anyone can contribute, and you don't need to know how to code.

## Two ways to add a resource

### 1. Suggest it (no code)

[Open an "Add a resource" issue](https://github.com/krmanik/english-immersion-library/issues/new?template=add-resource.yml) and fill in the form: link, category, a one-line description and level. A maintainer will add it.

### 2. Add it yourself (pull request)

1. Fork the repo and open the file for the right category in [`data/`](data/), for example `data/food.json`. The category ids are listed in [`categories.json`](categories.json).
2. Add an entry to the end of the list (see the [examples](#examples) below).
3. Run the scripts (Python 3.9 or newer; no packages needed):

   ```sh
   python3 scripts/enrich.py   # fills in feed, image and channel/podcast ids
   python3 scripts/build.py    # validates, then regenerates README.md, the website and the JSON
   ```

4. Commit everything that changed (`data/`, `README.md` and `dist/`) and open a pull request.

If you can't run the scripts, open the pull request anyway with only your `data/` change, and a maintainer will run them.

> **Don't edit the list in `README.md` or anything in `dist/` by hand.** They are generated from `data/`, and CI fails when they are out of sync.

## What belongs here

A resource should:

- **Be in English, or teach English.** Any variety of English is welcome: American, British, Australian, Canadian, Irish, New Zealand, Indian, South African and more.
- **Be official, licensed or original.** Use the creator's own channel or the rights holder's site.
- **Be useful to a learner** at some level, including native-level content for advanced learners.
- **Still be active or worth keeping as an archive.** Say "archive" in the description if it no longer updates.

Please don't add:

- Piracy sites, unofficial re-uploads of shows or films, or free e-book/comic aggregators of copyrighted work
- Adult content, gambling, or scams
- Pages that need a paid account before you can see anything (paid services with a free tier are fine; mark them `freemium` or `paid`)
- Your own product without saying so in the pull request (self-promotion is allowed if it's genuinely useful, and disclosed)
- Duplicates. Search `data/` for the URL or channel first.

## Fields

Required: `id`, `name`, `url`, `description`, `category`, `type`, `level`, `region`, `pricing`.

| Field | How to fill it |
|---|---|
| `id` | Lowercase letters, digits and dashes, unique across all files: `bbc-learning-english`, `sorted-food`. Never rename an existing id, because apps store it. |
| `name` | The name as the creator writes it. |
| `url` | Homepage or channel page. YouTube: `https://www.youtube.com/@handle`. Podcasts: `https://podcasts.apple.com/podcast/id<number>` |
| `description` | One short sentence, under 300 characters. Say what it is and why it helps. |
| `category` | Must match the file name, e.g. `food` in `data/food.json` |
| `type` | `website`, `youtube`, `podcast`, `app` or `newsletter` |
| `level` | Who can follow it: any of `beginner`, `intermediate`, `advanced`. Native content for adults is usually `["advanced"]`; slow, clear native content can be `["intermediate", "advanced"]`; kids' shows are `["beginner"]`. |
| `for_learners` | `true` only if it's made for people learning English |
| `region` | Where it's made, which usually means the accent you hear: `us`, `gb`, `au`, `ca`, `ie`, `nz`, `in`, `za`, `sg` or `global` (international or mixed) |
| `pricing` | `free`, `freemium` or `paid` |
| `platforms` | Any of `web`, `ios`, `android` |
| `tags` | Optional, lowercase kebab-case: `pronunciation`, `ielts`, `british-vs-american` |
| `login` | `none` if everything opens without an account, `partial` if some content or continued browsing needs a sign-in or app, `required` if you must sign in to see anything (defaults to `none`) |
| `subtitles` | Optional: `free` or `paid` when human-made English captions or transcripts exist as text. YouTube auto-captions and burned-in subtitles don't count. |
| `recommended` | Optional, maintainers only: `true` for picks (well-known, free, active, `login: none`) |
| `notes` | Optional caveats, e.g. "UK only." |

Leave out `feed`, `image` and `ids` and let `scripts/enrich.py` fill them in. For podcasts, add `"ids": {"apple_podcast_id": "<number>"}` if you know it; otherwise `enrich.py` searches Apple Podcasts by name and lists fuzzy matches for you to check.

The full schema is in [`schema/resource.schema.json`](schema/resource.schema.json).

## Examples

A YouTube channel (`data/food.json`):

```json
{
  "id": "sorted-food",
  "name": "Sorted Food",
  "url": "https://www.youtube.com/@SortedFood",
  "description": "Friends cook, compete and test gadgets.",
  "category": "food",
  "type": "youtube",
  "level": ["intermediate", "advanced"],
  "region": "gb",
  "pricing": "free",
  "platforms": ["web", "ios", "android"]
}
```

A podcast for learners (`data/learn_podcast.json`):

```json
{
  "id": "6-minute-english",
  "name": "6 Minute English",
  "url": "https://podcasts.apple.com/podcast/id<number>",
  "description": "BBC discussions of a topical subject with key vocabulary, with transcripts on the BBC site.",
  "category": "learn_podcast",
  "type": "podcast",
  "level": ["beginner", "intermediate"],
  "for_learners": true,
  "region": "gb",
  "pricing": "free",
  "subtitles": "free"
}
```

## Fixing or removing an entry

- **Broken link or moved channel:** update `url` and run `enrich.py --force --only youtube` (or the matching type) to refresh its feed.
- **Wrong level or category:** edit the fields. To move an entry to another category, move the object to that file and change `category`; keep the same `id`.
- **Dead resource:** delete the object and say why in the pull request.

## Proposing a new category

Open an issue first. A new category needs an entry in `categories.json` (`id`, `group`, `name`, an [SF Symbols](https://developer.apple.com/sf-symbols/) `icon`, a [Lucide](https://lucide.dev) `web_icon` vendored in `vendor/lucide/`, and `description`), a matching `data/<id>.json`, and at least five resources.

## Checks

On every pull request, CI runs `python3 scripts/build.py --check`, which fails on:

- missing or invalid fields, unknown categories, or duplicate ids
- the same URL twice in one category
- `README.md`, `dist/index.html` or `dist/v1/` not regenerated after a data change

`python3 scripts/check_links.py` checks every link. It is also run weekly. Sites that block bots or are region-locked show as `blocked` or `unreachable` and are not treated as broken.
