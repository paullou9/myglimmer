# Deferred: persistent custom usernames + session_id leak mitigation

Status: **designed, fully implemented, and verified in preview — then rolled back out of
`index.html`** so the FAB / compose-modal / open-feed / one-per-day ship could go out alone.
This doc is the artifact to re-apply both features later. The Supabase objects are already
created (see §1.4) and can be left in place untouched — they are inert until the client code
below calls them.

Single file throughout: `/Users/paullou/code/myglimmer/index.html` (vanilla JS + Supabase).

---

## Part 1 — Persistent, user-chosen usernames

### 1.1 Goal / behavior
- Today the username lives in `sessionStorage` and resets each tab; it's a random
  `adjective_noun` (20×20 = 400 combos).
- Wanted: on first landing the user is prompted to **commit** to a randomly-generated name
  (with a shuffle toggle); the name **persists across sessions**; the generator yields
  **≥1,000,000** combinations; the name **backfills onto the user's past glimmers**; and it
  can be **changed later**. Names must be **globally unique** (no two people share one).
- Decisions made: three-word names; rename via tapping the name in the compose modal;
  first-run picker is a **once-in-a-lifetime gate** (shows once per browser, including for
  existing users with past posts); commit modal carries three disclaimers.

### 1.2 Generator (≥1M, three words, distinct adjectives)
Replace the wordlists + `generateUsername()`. 120 adjectives × 119 × 100 nouns = **1,428,000**.

```js
const adjectives = ['wandering','golden','quiet','morning','gentle','luminous','soft','drifting','amber','rosy','silver','tender','wild','coastal','misty','velvet','sunlit','breezy','dreamy','mossy','hazy','autumn','wintry','summer','verdant','dusky','dawn','twilight','glowing','shimmering','whispering','falling','rising','floating','gleaming','frosted','dewy','sleepy','cozy','warm','cool','crisp','fleeting','faded','bright','pale','deep','hidden','secret','distant','humble','noble','weathered','ancient','fresh','young','still','restless','roaming','settled','woven','tangled','smooth','rugged','hollow','brimming','fragrant','fragile','sturdy','swaying','curling','trembling','blushing','beaming','murmuring','lilac','indigo','crimson','scarlet','ashen','snowy','sandy','pebbled','clouded','starlit','moonlit','sunbaked','windswept','honeyed','sugared','spiced','salted','buttery','downy','feathered','fuzzy','plush','woolen','linen','glassy','dappled','speckled','freckled','brindled','russet','ochre','sage','olive','ferny','jade','teal','slate','pearl','opal','ivory','dusty','mellow','lush','placid','serene'];
const nouns = ['sparrow','fig','kumquat','meadow','pebble','lantern','birch','current','ember','fern','crest','willow','bloom','cedar','brook','heron','vale','clover','solstice','dune','thicket','hollow','grove','orchard','harbor','cove','lagoon','marsh','fjord','glacier','summit','ridge','canyon','prairie','tundra','oasis','delta','reef','isle','atoll','maple','aspen','spruce','alder','hazel','rowan','elm','poplar','sycamore','magnolia','jasmine','lavender','marigold','poppy','daisy','lupine','thistle','heather','bracken','reed','finch','wren','robin','swallow','plover','egret','osprey','kestrel','lark','thrush','otter','marten','badger','hare','fawn','vole','lynx','stoat','ferret','marmot','beacon','hearth','cottage','cabin','cairn','trellis','lattice','quilt','kettle','saucer','teacup','acorn','conker','chestnut','pinecone','seedling','sapling','blossom','petal','dewdrop'];

// adjective_adjective_noun with two *distinct* adjectives.
function generateUsername() {
  const i = Math.floor(Math.random() * adjectives.length);
  let j = Math.floor(Math.random() * (adjectives.length - 1));
  if (j >= i) j++; // skip i so the two adjectives never match
  const n = Math.floor(Math.random() * nouns.length);
  return adjectives[i] + '_' + adjectives[j] + '_' + nouns[n];
}
console.assert(adjectives.length * (adjectives.length - 1) * nouns.length >= 1e6,
  'username space is under 1,000,000 combinations');
```
`getAvatarEmoji` / `getAvatarColor` already hash arbitrary strings — no change needed.

### 1.3 Persistence + picker JS
Replace the old `sessionStorage` username init and `regenerateUsername()` with:

```js
const USERNAME_KEY = 'glimmer_username';
const USERNAME_COMMITTED_KEY = 'glimmer_username_committed';
function hasCommittedUsername() { return localStorage.getItem(USERNAME_COMMITTED_KEY) === '1'; }

let myUsername = localStorage.getItem(USERNAME_KEY) || generateUsername();

function renderMyUsername() {
  document.getElementById('myAvatar').textContent = getAvatarEmoji(myUsername);
  document.getElementById('myAvatar').style.background = getAvatarColor(myUsername);
  document.getElementById('myUsernameDisplay').textContent = myUsername;
}
renderMyUsername();
applyPromptPlaceholder();

let candidateName = myUsername;
function renderCandidate() {
  document.getElementById('pickerAvatar').textContent = getAvatarEmoji(candidateName);
  document.getElementById('pickerAvatar').style.background = getAvatarColor(candidateName);
  document.getElementById('pickerName').textContent = candidateName;
}
function shuffleCandidate() { candidateName = generateUsername(); renderCandidate(); }

function openUsernamePicker(mode) {
  candidateName = hasCommittedUsername() ? myUsername : generateUsername();
  renderCandidate();
  const overlay = document.getElementById('usernameModal');
  overlay.classList.toggle('commit-mode', mode === 'commit');
  overlay.classList.toggle('rename-mode', mode === 'rename');
  document.getElementById('pickerCommitBtn').textContent = mode === 'commit' ? 'This is me' : 'Save name';
  overlay.classList.add('open');
}
function closeUsernamePicker() {
  if (!hasCommittedUsername()) return; // first-run gate can't be dismissed
  document.getElementById('usernameModal').classList.remove('open');
}

async function commitUsername() {
  const isRename = hasCommittedUsername();
  if (isRename && candidateName === myUsername) {
    document.getElementById('usernameModal').classList.remove('open'); return;
  }
  const btn = document.getElementById('pickerCommitBtn');
  btn.disabled = true;
  const ok = await claimUsername(candidateName);
  btn.disabled = false;
  if (!ok) { showToast('That name is taken — here\'s another ✦'); shuffleCandidate(); return; }
  myUsername = candidateName;
  localStorage.setItem(USERNAME_KEY, myUsername);
  localStorage.setItem(USERNAME_COMMITTED_KEY, '1');
  renderMyUsername();
  document.getElementById('usernameModal').classList.remove('open');
  showToast(isRename ? 'Your name is updated ✦' : `Welcome, ${myUsername} ✦`);
}

// Atomically claim a globally-unique name + backfill past posts, in one RPC.
async function claimUsername(name) {
  const { data, error } = await db.rpc('claim_username', { p_session_id: SESSION_ID, p_username: name });
  if (error) { showToast('Couldn\'t reach the server — try again?'); return false; }
  if (data === true) {
    await loadAllGlimmers();
    if (myGlimmersLoaded) await loadMyGlimmers();
    return true;
  }
  return false; // taken
}

// goCompose() should call openUsernamePicker is NOT needed; keep goCompose -> openCompose.
```

Boot gate (in `boot()`, after `loadAllGlimmers()`):
```js
// Once-in-a-lifetime: prompt every visitor to commit to a name.
if (!hasCommittedUsername()) openUsernamePicker('commit');
```

Compose username-row rewire (the `↻` + the name open the rename picker):
```html
<div class="username-display" id="myUsernameDisplay" onclick="openUsernamePicker('rename')" style="cursor:pointer;"></div>
<div style="...">tap to change your name</div>
<button class="regenerate-btn" onclick="openUsernamePicker('rename')" title="Change name" aria-label="Change name">↻</button>
```

### 1.4 Picker modal markup + CSS
Markup (next to `#reportModal`):
```html
<div class="modal-overlay" id="usernameModal">
  <div class="modal username-modal">
    <button class="compose-close picker-close" onclick="closeUsernamePicker()" aria-label="Close">✕</button>
    <h3 class="picker-title-commit">Pick your name</h3>
    <h3 class="picker-title-rename">Change your name</h3>
    <p class="picker-sub-commit">This is how you'll show up on every glimmer you share.</p>
    <div class="picker-preview">
      <div class="avatar picker-avatar" id="pickerAvatar"></div>
      <div class="picker-name" id="pickerName"></div>
    </div>
    <button class="picker-shuffle" onclick="shuffleCandidate()">↻ Try another</button>
    <ul class="picker-notes picker-notes-commit">
      <li>You can change this name anytime.</li>
      <li>It stays the same across visits unless you change it.</li>
      <li>Changing it updates the name on all your past glimmers too.</li>
    </ul>
    <p class="picker-notes picker-notes-rename">Changing your name updates it on all your past glimmers too.</p>
    <div class="modal-actions picker-actions">
      <button class="btn-secondary picker-cancel" onclick="closeUsernamePicker()">Cancel</button>
      <button class="submit-btn" id="pickerCommitBtn" onclick="commitUsername()">This is me</button>
    </div>
  </div>
</div>
```
CSS (mode visibility is the key part — commit hides rename bits + the dismiss affordances):
```css
.username-modal { position: relative; text-align: center; max-width: 400px; }
.username-modal h3 { text-align: center; }
.picker-close { top: -14px; right: -14px; }
.picker-preview { display:flex; flex-direction:column; align-items:center; gap:12px; margin:8px 0 16px; }
.picker-avatar { width:60px; height:60px; font-size:28px; }
.picker-name { font-family:'DM Sans',sans-serif; font-size:19px; font-weight:500; color:var(--ink); word-break:break-word; }
.picker-shuffle { background:none; border:1px solid var(--border); border-radius:100px; padding:8px 18px; font-family:'DM Sans',sans-serif; font-size:13px; color:var(--ink-light); cursor:pointer; transition:all .15s; }
.picker-shuffle:hover { background:var(--cream); color:var(--ink); }
.picker-notes { text-align:left; font-size:12.5px; color:var(--ink-light); line-height:1.6; margin:18px 0 4px; }
ul.picker-notes { padding-left:18px; } ul.picker-notes li { margin-bottom:4px; }
.picker-actions { margin-top:20px; align-items:center; }
#usernameModal.commit-mode .picker-title-rename,
#usernameModal.commit-mode .picker-notes-rename,
#usernameModal.commit-mode .picker-close,
#usernameModal.commit-mode .picker-cancel,
#usernameModal.rename-mode .picker-title-commit,
#usernameModal.rename-mode .picker-sub-commit,
#usernameModal.rename-mode .picker-notes-commit { display: none; }
```

### 1.5 Supabase objects — ALREADY CREATED (safe to leave)
Run once (already done in the SQL editor). Inert until `claim_username` is called by the
client. Enforces global uniqueness (`username` PK) and one-name-per-session (`session_id`
unique), and backfills `glimmers` + `comments` in the same call. `set_username` from an
earlier iteration is **superseded** by this — don't use it.

```sql
create table if not exists usernames (
  username   text primary key,
  session_id uuid not null unique,
  updated_at timestamptz not null default now()
);

create or replace function claim_username(p_session_id uuid, p_username text)
returns boolean language plpgsql security definer set search_path = public as $$
declare owner uuid;
begin
  select session_id into owner from usernames where username = p_username;
  if owner is not null and owner <> p_session_id then
    return false;                              -- taken by someone else
  end if;
  insert into usernames (session_id, username)
  values (p_session_id, p_username)
  on conflict (session_id) do update set username = excluded.username, updated_at = now();
  update glimmers set username = p_username where session_id = p_session_id;
  update comments set username = p_username where session_id = p_session_id;
  return true;
exception when unique_violation then
  return false;                                -- lost a concurrent race for the name
end;
$$;
grant execute on function claim_username(uuid, text) to anon;
```

### 1.6 Notes / non-goals
- Generator only (no free-text) → no profanity/length validation; the RPC only ever receives
  generator output.
- Uniqueness is **going-forward**: historical posts under old random names aren't in the
  registry, so pre-existing duplicates remain until those users commit (then they claim a
  unique name and their history backfills).
- Collisions handled reactively at commit time (rare at 1.4M combos), not pre-filtered.
- Backfill difficulty is **low**: `username` is denormalized on every row and `session_id`
  is a stable per-browser UUID, so a rename is one `UPDATE … WHERE session_id = …` — the
  only reason it goes through an RPC is that anon can't UPDATE `glimmers` directly (same as
  `increment_hearts`).

---

## Part 2 — session_id leak mitigation (the "low-risk half")

### 2.1 Root cause
`session_id` is the de-facto identity (a stable per-browser UUID in `localStorage`) and is
**trusted as a bearer token** by the RPCs (`claim_username`, `increment_hearts`,
`increment_comments`) — they take it as a parameter and never verify it. Meanwhile the feed
queries used `.select('*')`, which **returns `session_id` to every visitor**, and the
`anon` key is public — so a single `curl` against `/rest/v1/glimmers?select=session_id` dumps
every device's identity. A published bearer token isn't a secret.

### 2.2 The low-risk client fix (implemented, then reverted)
Stop returning `session_id` in feed responses; determine ownership ("delete" vs "report")
from a locally-tracked set of the user's own glimmer ids instead.

```js
// Allowlist — never select session_id into the public feed.
const FEED_COLUMNS = 'id, username, text, hearts, comments, created_at';
// fetchPage() and loadMyGlimmers() use .select(FEED_COLUMNS); loadComments uses
// .select('id, username, text, created_at').

// Own-glimmer tracking (replaces post.session_id === SESSION_ID in the card render).
const myGlimmerIds = new Set(JSON.parse(localStorage.getItem('glimmer_mine') || '[]'));
function rememberMyGlimmer(id) {
  if (!id || myGlimmerIds.has(id)) return;
  myGlimmerIds.add(id);
  localStorage.setItem('glimmer_mine', JSON.stringify([...myGlimmerIds]));
}
function isMyGlimmer(post) { return myGlimmerIds.has(post.id); }
async function loadMyGlimmerIds() { // boot, before loadAllGlimmers()
  const { data } = await db.from('glimmers').select('id').eq('session_id', SESSION_ID);
  if (data) data.forEach(r => rememberMyGlimmer(r.id));
}
```
- Card render: `${isMyGlimmer(post) ? deleteBtn : reportBtn}`.
- `submitGlimmer` success + own realtime inserts call `rememberMyGlimmer(...)`.
- Filtering by your *own* `session_id` (My Glimmers, `loadMyGlimmerIds`) is fine — it only
  ever returns your own rows.

### 2.3 Residual exposure (NOT closeable client-side)
The realtime channel still delivers full rows — including `session_id` — to every subscriber
as new posts arrive. A client holding an open websocket can still collect `session_id`s of
posts made *while it listens*, one at a time. Closing this needs DB-side work: restrict the
realtime publication's columns / adjust replica identity for `glimmers` (and `comments`).

### 2.4 Real fix (production hardening)
Stop trusting a client-supplied identifier; derive identity server-side:
1. Add Supabase Auth (anonymous sign-in is enough) → every user gets a JWT / `auth.uid()`.
2. Drop the `session_id` parameter from RPCs; use `auth.uid()` internally so a caller can
   only act as themselves.
3. Enforce RLS by `auth.uid()` on `glimmers`/`comments` update + delete.
4. Never select identity columns into the feed (the §2.2 allowlist already does this).
5. Optional: rate-limit the increment RPCs to blunt count inflation.

---

## Re-apply order
1. Confirm Supabase objects from §1.5 exist (they do).
2. Apply Part 1 (generator → persistence/picker JS → picker modal markup+CSS → compose
   username-row rewire → boot gate).
3. Apply Part 2 (FEED_COLUMNS + ownership set + boot `loadMyGlimmerIds`).
4. Verify: fresh `localStorage` shows the commit gate once; shuffle + commit persist across
   reloads; rename fires `claim_username` and backfills; a second browser can't claim a taken
   name; feed responses contain no `session_id`.
