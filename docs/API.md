# English Immersion Library: JSON API

A curated, filterable JSON directory of **English-language content for learners**: YouTube channels, podcasts, news sites, talk shows, explainers, web fiction, comics, music, kids' content, dictionaries, apps and more.

It powers the Discover tab in [Engly Reader](https://krmanik.github.io/engly-reader-app/), but it's plain static JSON, so any app or site can use it. It shares the v1 layout of the [Chinese Immersion Library](https://github.com/krmanik/chinese-immersion-library), so one client can read both.

- **%%COUNT%% resources** in **37 categories** (live counts in `index.json`)
- **%%FEEDS%% with a machine-readable feed** (YouTube channel feeds, podcast RSS, site RSS/Atom), ready for a "latest items" feed
- Filter by level, region (accent), pricing, type, tag, login needs and captions; `recommended` marks well-known picks that open without an account
- Validated in CI, served from GitHub Pages, no backend

## Endpoints

Base URL (GitHub Pages, after the first deploy):

```
https://krmanik.github.io/english-immersion-library/v1/
```

| Path | Contents |
|---|---|
| `index.json` | Manifest: `data_version`, the category list (with counts, icons and paths) and the facet values available for filtering |
| `all.json` | Every resource |
| `feeds.json` | Only resources that have a feed: `{id, name, category, type, feed, image}` |
| `categories/{id}.json` | One category, e.g. `categories/news.json` |

`v1` is the API version. Breaking schema changes go to `v2/`, so app builds already shipped keep working.

### Other ways to fetch the same files

| Option | URL | Notes |
|---|---|---|
| **GitHub Pages** (recommended) | `https://krmanik.github.io/english-immersion-library/v1/all.json` | CDN, gzip, `Access-Control-Allow-Origin: *`, about 10 min cache. Updates on every push to `main`. |
| **jsDelivr** | `https://cdn.jsdelivr.net/gh/krmanik/english-immersion-library@main/dist/v1/all.json` | Global CDN. Branch URLs are cached up to 12 h. Pin a tag (`@v1.0.0`) for immutable URLs, or purge with `https://purge.jsdelivr.net/gh/krmanik/english-immersion-library@main/dist/v1/all.json`. |
| **raw.githubusercontent.com** | `https://raw.githubusercontent.com/krmanik/english-immersion-library/main/dist/v1/all.json` | Simplest. 5 min cache, rate-limited, served as `text/plain`. Good for testing. |

Clients should cache the response and compare `data_version` (a content hash that changes only when the data changes) instead of downloading `all.json` every launch. GitHub Pages also sends an `ETag`, so `If-None-Match` requests return `304 Not Modified`.

## Resource schema

Full JSON Schema: [`schema/resource.schema.json`](../schema/resource.schema.json).

```json
%%EXAMPLE%%
```

| Field | Values |
|---|---|
| `type` | `website` `youtube` `podcast` `app` `newsletter` |
| `level` | any of `beginner` `intermediate` `advanced`. Native content is usually `advanced`; kids' content is `beginner`. |
| `for_learners` | `true` when made for learners of English (graded, slow or explained) |
| `region` | `us` `gb` `au` `ca` `ie` `nz` `in` `za` `sg` `global`: where it's made, which usually means the accent |
| `pricing` | `free` `freemium` `paid` |
| `feed.format` | `youtube` (Atom), `podcast` (RSS), `rss`, `atom` |
| `login` | `none` (opens without an account), `partial` (some content, full quality or continued browsing needs a sign-in, app or payment), `required` |
| `subtitles` | `free` or `paid` when human-made English captions or transcripts exist as text; omitted when none or unknown. YouTube auto-captions don't count. |
| `recommended` | `true` for picks: well-known, free, active and `login: none`. Good default shelf for an app. |
| `notes` | Caveats such as region locks |

`id`s are stable: once published, an id is never renamed, so apps can store bookmarks and "followed" state by id.

### Compatibility with the Chinese Immersion Library

The envelope (`index.json`, `all.json`, `feeds.json`, `categories/{id}.json`) and field names are the same. The Chinese-only fields `script`, `dialect`, `language` and `name_zh` are not used here, and `region` takes English-speaking country codes. A client that treats those fields as optional can read both libraries.

## Categories

Grouped in `categories.json` as **learn**, **read**, **watch** and **listen**. Each category has an `icon` (an SF Symbols name) so an iOS app can render it directly, and a `web_icon` (Lucide).

| Group | Categories |
|---|---|
%%CATS%%

## Using it from Swift

```swift
struct Feed: Decodable { let format: String; let url: URL }
struct Resource: Decodable, Identifiable {
    let id, name, description, category, type, region, pricing: String
    let url: URL
    let level: [String]
    let tags: [String]
    let forLearners: Bool
    let feed: Feed?
    let image: URL?
}
struct AllResponse: Decodable { let dataVersion: String; let resources: [Resource] }

func loadResources() async throws -> [Resource] {
    let url = URL(string: "https://krmanik.github.io/english-immersion-library/v1/all.json")!
    var request = URLRequest(url: url)
    request.cachePolicy = .reloadRevalidatingCacheData   // uses ETag, gets 304 when unchanged
    let (data, _) = try await URLSession.shared.data(for: request)
    let decoder = JSONDecoder()
    decoder.keyDecodingStrategy = .convertFromSnakeCase
    return try decoder.decode(AllResponse.self, from: data).resources
}

// Filtering example: beginner-friendly, made for learners, British English
let resources = try await loadResources()
let picks = resources.filter { $0.forLearners && $0.level.contains("beginner") && $0.region == "gb" }
```

## Repository layout

```
README.md                  intro (hand-written) + the full list (generated between markers)
CONTRIBUTING.md            how to add or fix resources
categories.json            category ids, names, icons, groups (order = display order)
data/<category>.json       the source of truth: edit these
schema/                    JSON Schema for one resource
scripts/build.py           validate data/, generate dist/ and the README list (no dependencies)
scripts/render.py          README list + GitHub Pages site templates
scripts/enrich.py          resolve YouTube channel ids, podcast RSS, artwork, site RSS, captions
scripts/check_links.py     check every URL (and feed with --feeds)
dist/index.html            generated website with search and filters (GitHub Pages root)
dist/v1/                   generated JSON API: do not edit by hand
```

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md). CI runs `build.py --check` on every push and pull request (fails on invalid data or stale generated files), then deploys `dist/` to GitHub Pages. A weekly workflow runs `check_links.py` and uploads a report.

## How the list was built

Seeded from well-known learner resources (BBC Learning English, VOA Learning English, British Council and others) and the Chinese Immersion Library's category plan, then extended across native genres and English-speaking countries. Every YouTube channel was resolved from its handle page and its title checked against the entry name, every podcast through the iTunes Search/Lookup API, site feeds were discovered from page headers, and every URL was link-checked. Entries that did not resolve were fixed or removed.

## License

Code is MIT. The data (names, descriptions and links) is CC0. Linked content belongs to its owners.
