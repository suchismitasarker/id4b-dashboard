"""
chess_signals.py — shared CHESS/ID4B live-signal helpers.

Meant to be imported by more than one script: the SPEC Dashboard's Summary
tab (spec_dashboard_qt.py, this package) uses the SPEC-file half of this
module to show live CESR/IC1/IC2/diode/Flow readouts; a Slack-bot-style monitor
script (in the style of chess_beam_monitor_ai.py) could import the network
half to poll signals.chess.cornell.edu directly. Keeping both in one place
means the PV names, multipliers, and endpoint format only need to be gotten
right (and fixed, if they change) in one spot.

Two independent ways to get the beam-monitor numbers (CESR, IC1, IC2, diode,
Flow), used together with SPEC-file-first priority:

1. SPEC-file column matching (`get_spec_live_values` / `match_spec_columns`)
   — always available offline, reads the latest row of whatever SPEC file is
   currently loaded. Column names aren't assumed to be numbered consistently
   between experiments/SPEC files (a real concern the user raised — "SPEC
   will not always number"), so channels are matched by flexible,
   case-insensitive name patterns (CHANNEL_NAME_PATTERNS) rather than fixed
   column positions.

2. Direct network polling of signals.chess.cornell.edu
   (`ChessSignalsClient.get_values`) — opt-in only, since that host is only
   reachable from on-site/the CHESS network (confirmed unreachable from the
   dashboard-development sandbox this file was written in — every attempt to
   reach signals.chess.cornell.edu or new-status.chess.cornell.edu from
   there failed with an egress-blocked error).

   PV names/multiplier history (read this before touching BEAM_PV_MAP):
   the user first shared a temperature-only script (ChessLiveDataExtractor
   / ChessBot) covering just ID4B_CRYOGL_STG1_T/SAM_T/STG2_T -- nothing
   about CESR/IC1/IC2/diode -- and probing ~12 guessed URL patterns rather
   than one confirmed endpoint. An earlier version of this module wrongly
   claimed the ID4B_CNT00/02/03_VLT -> IC1/IC2/diode mapping and x10000
   multiplier below were "confirmed working" from that script -- they
   weren't; that was a mistake, later corrected to all `pv=None`. The user
   subsequently shared a second, fuller script (also ChessLiveDataExtractor
   / ChessBot) whose own ALL_PV_MAPPING dict *does* contain exactly this
   mapping -- ID4B_CNT00_VLT -> "Ion Chamber 1 (IC1)", ID4B_CNT02_VLT ->
   "Ion Chamber 2 (IC2)", ID4B_CNT03_VLT -> "Beam Stop Diode", each with
   multiplier 10000, fetched via a single confirmed `/plot/UPDATE_{pv}`
   request (not a multi-template guess) -- so IC1/IC2/diode below are now
   genuinely sourced from something the user shared, not fabricated. CESR
   was absent from every script the user shared; the user then separately
   told me directly in chat that CESR's PV is `ID4B_CNT01_VLT` (fitting the
   numbering gap between IC1's CNT00 and IC2's CNT02). That PV name is now
   wired in below, but -- unlike ic1/ic2/diode -- it did NOT come from a
   script's own mapping dict and I have not independently verified it
   (still can't reach either signals.chess.cornell.edu or
   new-status.chess.cornell.edu from this sandbox). The multiplier for
   cesr is also unknown and is left at 1 (no scaling) rather than assumed
   to match ic1/ic2/diode's x10000, since CESR (beam current, mA) is a
   different kind of reading than the ion-chamber/diode voltages. Worth
   sanity-checking the dashboard's live CESR number against
   new-status.chess.cornell.edu/ID4B (currently reading ~0.01 mA) once
   this is run on-site.

BEAM_PV_MAP: IC1/IC2/diode have real, user-confirmed PVs (from a script's
own mapping dict). CESR has a PV (ID4B_CNT01_VLT) the user told me directly
in chat, not independently verified, with an unconfirmed (placeholder 1x)
multiplier -- see above.

Also wired in (this round): the 3 cryostat temperature channels (stage1/
sample/stage2, TEMPERATURE_PV_MAP) as a second, parallel set of Summary-tab
readouts -- "the same as CESR/IC1/IC2/diode" per the user's request. These
PVs (ID4B_CRYOGL_STG1_T/SAM_T/STG2_T) are the most solidly-sourced in this
module: they're both what the user's very first script used AND what the
user separately re-typed/confirmed directly in chat, so there's no "told
me but unverified" caveat needed the way there is for CESR. Mirrors the
beam-channel machinery exactly (match_temperature_columns(),
get_spec_live_temperatures(), get_live_temperature_values()) rather than
reusing/overloading the beam-channel functions, so the two stay fully
independent and adding temperature support can't change beam-channel
behavior.

Also wired in (this round): a "flow" readout, after the user shared the
real SPEC macro that reads it (flow_get, in
.../Macros/surrena/aalborg_flow.mac -- "Aalborg" being a mass-flow-
controller brand, so this is very likely a cryostat/cryojet gas flow
reading). Unlike CESR or the temperature channels, this one is added to
the existing generic beam-channel machinery (CHANNEL_NAME_PATTERNS/
CHANNEL_LABELS/CHANNEL_ORDER/BEAM_PV_MAP) rather than given its own
parallel set of functions, since "flow" behaves exactly like a 5th beam
channel and that machinery is already fully generic over those dicts.
"flow" is a genuine, already-logged column in the sample SPEC data's own
#L header line (right alongside cesr/ic1/ic2/diode), so it works
immediately via the existing SPEC-file-column path with no other code
changes. The shared macro only shows a SPEC-internal function call
(flow = _flow_get()), not an HTTP endpoint or PV name, so unlike ic1/ic2/
diode/cesr there's no known network PV for it yet -- BEAM_PV_MAP's entry
for "flow" leaves pv=None, which ChessSignalsClient.get_values() skips
entirely (same treatment CESR got before its PV was known). If a real
signals.chess.cornell.edu PV for flow turns up, it can be added the same
way CESR's was.

Also wired in (this round): a real network PV for "energy" --
ID4B_MON_KEV, given directly by the user in chat, the same way CESR's PV
was. "energy" was previously SPEC-column-only (pv=None), which is why the
Overall Summary tab's Energy/Flux readouts stayed at "—" for the user even
with a SPEC file loaded that had no exactly-matching "energy"/"mono_energy"
column. With a real PV now wired in, the network fetch path (the "Try live
network fetch" checkbox, on by default) populates Energy directly, same as
CESR/IC1/IC2/Diode. "energy" was also moved from its own separate row into
CHANNEL_ORDER, so it now displays inside the same Beam Condition card row
as CESR/IC1/IC2/Diode rather than a standalone "X-ray Flux" section -- the
computed Flux number (not a raw channel) is still shown separately, right
below that row, since it depends on Energy + IC1 together rather than
being a channel of its own.

Also wired in (this round, later fully reverted -- see next paragraph):
EPICS Channel Access (via the optional `pyepics` package) as a preferred
read path for BEAM_PV_MAP, then narrowed to just "energy", then batched
via caget_many(). None of it worked cleanly on-site (lnx306): repeated
"couldn't be located" caRepeater warnings, "cannot connect" lines, and --
worse -- since the fetch was being called synchronously from
_beam_signals_tick() (spec_dashboard_qt.py's 1s QTimer, on the main Qt
thread), every EPICS call that took a few seconds froze the entire GUI
for that long ("opens but not workable"). The user explicitly asked to
go back to the previous, HTTP-only logic that was at least partially
working, and separately confirmed (via a live SPEC session, `caget
ID4B_MON_KEV` at a real terminal) that Energy genuinely is a normal,
readable EPICS PV on-site -- so EPICS itself isn't the problem; calling
it synchronously, once per PV, on every single 1s GUI tick was.

THIS MODULE IS NOW FULLY HTTP-ONLY AGAIN (no `epics`/`pyepics` import
anywhere in this file, no `prefer_epics` parameter, no fetch_epics()/
fetch_epics_many()) -- ChessSignalsClient.get_values() and
get_live_beam_values() are back to exactly the same single
signals.chess.cornell.edu code path they used before any EPICS work
started, for every channel including "energy" (BEAM_PV_MAP still carries
energy's ID4B_MON_KEV entry, so it's tried over HTTP too -- harmless, and
worth leaving in case that endpoint ever does respond for it).

Live Energy over EPICS is still wanted (the Ion Chamber Flux calculator
needs it, and the user confirmed the PV works), so it now lives entirely
in spec_dashboard_qt.py instead, as a small dedicated background
`QThread` (see EnergyEpicsFetchThread there) that:
  - imports `epics` and calls `epics.caget("ID4B_MON_KEV", ...)` directly,
    but only as a ONE-SHOT read -- run() does a single caget() and returns,
    it is not a loop. The thread is only ever instantiated rarely (once at
    GUI startup, and again only when the user clicks the "Refresh Energy"
    button on the Summary tab), per the user's explicit instruction to
    read Energy "only one time"/"only when needed", not continuously. This
    is what actually avoids the repeated caRepeater-spawn attempts and the
    per-tick blocking -- there simply is no per-tick EPICS call anymore.
  - runs on its own QThread (separate from the Qt main thread), so even a
    slow or hanging caget() can never freeze the GUI while it's in flight.
  - is completely independent of the 1s _beam_signals_tick() timer, which
    just reads whatever Energy value the last one-shot fetch cached (or
    "—" if none has completed yet).
  - uses leading_number() (still here, below) to parse caget(as_string=True)'s
    text reply (e.g. "45.000 keV") the same way the old fetch_epics() did.
This keeps chess_signals.py itself simple, dependency-light, and fully
HTTP/CESR-IC1-IC2-diode-focused, matching the "previous logic where
things were working" baseline, while still getting a genuinely live
Energy reading, read only on demand rather than continuously.
"""

import re
from typing import Dict, List, Optional

BASE_URL = "http://signals.chess.cornell.edu"

# The full ID4B status page (as opposed to signals.chess.cornell.edu's raw
# PV endpoint above) -- shows a human-readable current status message
# (things like "Investigating", "Refilling", "Beam Lost", operator notes,
# etc.) alongside the CESR mA reading. Used by fetch_beam_status_message()
# below so Slack alerts can include that text, not just a generic "No
# Beam"/"Beam Restored" line.
NEW_STATUS_URL = "http://new-status.chess.cornell.edu/ID4B"

# Regex patterns tried, in order, to pull the current status text out of
# the new-status page's HTML. This page's exact markup has not been
# directly inspected from this sandbox -- new-status.chess.cornell.edu is
# unreachable from here, same as signals.chess.cornell.edu (see
# ChessSignalsClient's docstring below) -- so this tries a few plausible
# id="statusmsgnow"-style patterns rather than assuming one exact
# tag/structure. If none of these match the page's real markup once run
# on-site, only this list needs updating -- everything that calls
# fetch_beam_status_message() just treats "no match" the same as "page
# unreachable" (returns None, alert falls back to the generic text).
_STATUS_MESSAGE_PATTERNS = [
    re.compile(r'id=["\']statusmsgnow["\'][^>]*>(.*?)<', re.IGNORECASE | re.DOTALL),
    re.compile(r'id=["\']statuscache["\'][^>]*>(.*?)<', re.IGNORECASE | re.DOTALL),
    re.compile(r'statusmsgnow["\']?\s*[:=]\s*["\'](.*?)["\']', re.IGNORECASE),
]


def fetch_beam_status_message(
    url: str = NEW_STATUS_URL, timeout: float = 5.0, session=None
) -> Optional[str]:
    """GET new-status.chess.cornell.edu/ID4B and pull out the current
    status message text (whatever populates the page's #statusmsgnow
    element -- things like "Investigating", "Refilling", "Beam Lost",
    operator names, etc.), so Slack alerts can include it alongside the
    plain "No Beam"/"Beam Restored" text. `requests` is imported lazily
    (like ChessSignalsClient below) so the rest of this module keeps
    working even where `requests` isn't installed.

    Only reachable from on-site/the CHESS network -- returns None on any
    failure (unreachable, non-200, no pattern match, requests not
    installed, ...) rather than raising, so a failed fetch just means the
    Slack alert falls back to the generic text instead of breaking the
    alert entirely.

    NOTE: this page may render its status text via JavaScript after the
    initial page load rather than including it in the raw HTML response --
    the user's own original monitoring script read it via a full headless-
    Chromium browser (Playwright), not a plain HTTP GET, which suggests
    this may be the case. A plain GET + regex, as done here, only finds
    the text if it's actually present in the HTML that comes back from the
    GET itself. If this always returns None once run on-site even though
    the page clearly shows a message, that's the most likely reason -- the
    fix would be to swap this for a Playwright-based fetch instead (a much
    heavier dependency, so not the default here)."""
    try:
        import requests

        sess = session
        if sess is None:
            resp = requests.get(
                url,
                timeout=timeout,
                headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"},
            )
        else:
            resp = sess.get(
                url,
                timeout=timeout,
                headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"},
            )
    except Exception:
        return None
    if getattr(resp, "status_code", None) != 200:
        return None
    html = resp.text
    for pattern in _STATUS_MESSAGE_PATTERNS:
        match = pattern.search(html)
        if match:
            text = re.sub(r"<[^>]+>", "", match.group(1)).strip()
            if text:
                return text
    return None

# "No beam"/"beam restored" detection for the Summary tab's banner (and
# the Slack "No Beam"/"Beam Restored" alerts, which reuse the exact same
# result via is_no_beam()). Two SEPARATE cutoffs with hysteresis, rather
# than one shared threshold that flips the state the instant CESR crosses
# it either way: a single 1.4 mA cutoff meant a "Beam Restored" alert
# could fire (or flap back to "No Beam" and re-fire "Restored" again)
# purely from CESR sitting anywhere near that one number, without it
# needing to have actually gone all the way down to a genuine no-beam
# level first. With two cutoffs and a dead zone in between:
#   - below NO_BEAM_CESR_THRESHOLD (0.05 mA)       -> confirmed no beam
#   - at/above BEAM_RESTORED_CESR_THRESHOLD (1.4mA) -> confirmed beam back
#   - anywhere in between (0.05-1.4 mA)             -> state doesn't change;
#     stays whatever it already was until CESR actually reaches one of the
#     two real cutoffs, so a reading merely passing through the middle
#     can't flip anything on its own.
# Both are still placeholders, not confirmed CHESS specs -- worth
# revisiting once CESR's PV/multiplier are independently verified (see
# BEAM_PV_MAP above), since the multiplier is currently an unconfirmed 1x
# and could change what these should mean numerically.
NO_BEAM_CESR_THRESHOLD = 0.05
BEAM_RESTORED_CESR_THRESHOLD = 1.4


def is_no_beam(cesr_value: Optional[float], previous_no_beam: Optional[bool] = None) -> bool:
    """Hysteresis-based no-beam/beam-restored detection -- see the cutoffs'
    docstring above for the 0.05 mA / 1.4 mA / dead-zone logic. Needs the
    PREVIOUS tick's no-beam state (`previous_no_beam`) to know what to
    return while CESR is sitting in the 0.05-1.4 mA dead zone, or while
    there's no reading at all (`cesr_value=None` -- no matching SPEC
    column, network fetch off/failed): in both cases the state just
    carries forward unchanged rather than being decided from scratch.
    `previous_no_beam=None` (no prior tick to compare against -- app just
    started) is treated as an implicit "beam present" baseline, the same
    assumption _maybe_alert_beam_slack() makes on its own first tick, so
    launching mid-dead-zone or with no reading yet doesn't get treated as
    a confirmed no-beam state out of nowhere."""
    baseline = bool(previous_no_beam) if previous_no_beam is not None else False
    if cesr_value is None:
        return baseline
    abs_value = abs(cesr_value)
    if abs_value < NO_BEAM_CESR_THRESHOLD:
        return True
    if abs_value >= BEAM_RESTORED_CESR_THRESHOLD:
        return False
    return baseline

# ---------------------------------------------------------------------
# SPEC-file column matching
# ---------------------------------------------------------------------

# Canonical channel name -> list of lowercase substrings to match against
# SPEC column headers. Checked in order; the first pattern that matches
# ANY column (exact match first, then substring) wins. Extend these lists
# if a particular beamline/SPEC file uses a different naming convention.
#
# "flow" added after the user shared a real SPEC macro that reads it
# (`flow_get`, in .../Macros/surrena/aalborg_flow.mac -- "Aalborg" being a
# mass-flow-controller brand, so this is very likely a cryostat/cryojet gas
# flow reading). Unlike CESR, this one didn't need any guessing: "flow" is
# already a genuine logged column in the sample SPEC data's own #L header
# line (right alongside cesr/ic1/ic2/diode/sampleT), so it's matched via
# the same SPEC-file-column path those channels use, no PV needed for that
# to work. The macro itself only shows a SPEC-side call
# (`flow = _flow_get()`) -- not an HTTP endpoint/PV name -- so unlike ic1/
# ic2/diode/cesr there's currently no known network PV for it; BEAM_PV_MAP
# below leaves flow's pv as None (skipped entirely by
# ChessSignalsClient.get_values(), same as every other channel started out
# before its PV was known). If there's a signals.chess.cornell.edu PV for
# flow, it can be added the same way CESR's was.
# "energy" added for the Ion Chamber Flux feature (Overall Summary tab's
# Beam Condition row + the dedicated Ion Chamber Flux tab, both of which
# need a live beam energy in keV to run ion_chamber_flux.ion_chamber_flux()).
# Matched the same way as the other channels, against whatever the loaded
# SPEC file's own column happens to be named -- "energy"/"Energy" is a
# common motor/column name at CHESS for the monochromator energy. The user
# has since given a confirmed network PV for this (ID4B_MON_KEV -- see
# BEAM_PV_MAP below), so the SPEC-column path here is now the fallback,
# not the only source.
CHANNEL_NAME_PATTERNS: Dict[str, List[str]] = {
    "cesr": ["cesr"],
    "ic1": ["ic1", "ion_chamber1", "ion_chamber_1", "ionchamber1"],
    "ic2": ["ic2", "ion_chamber2", "ion_chamber_2", "ionchamber2"],
    "diode": ["diode", "pin_diode", "pindiode", "beam_stop_diode", "beamstopdiode"],
    "flow": ["flow", "gas_flow", "flow_rate", "cryo_flow"],
    "energy": ["energy", "mono_energy", "monoenergy", "beam_energy", "beamenergy"],
    # "mostab" -- the user's explicit display label for a new Beam
    # Condition card reading ID4B_CNT06_VLT (counter #6 in the same
    # ID4B_CNTnn_VLT family as ic1=CNT00/cesr=CNT01/ic2=CNT02/diode=CNT03).
    # "mostab" was NOT a typo -- the user confirmed via AskUserQuestion
    # that "Mostab" is the literal label they want, so the SPEC-column
    # match patterns below cover the label itself plus the raw PV name in
    # case a loaded SPEC file happens to log this column under either
    # spelling. See BEAM_PV_MAP below for the network PV/scaling notes.
    "mostab": ["mostab", "cnt06", "id4b_cnt06_vlt"],
}

# Display order + labels for the Summary tab readouts. "flow" -> "Flow
# Rate" per the user's explicit renaming request; note the *value*-fetching
# side (CHANNEL_NAME_PATTERNS key, BEAM_PV_MAP entry, get_live_beam_values()
# result key) is still the lowercase "flow" canonical name -- only this
# display label changed, so nothing else needed to change to pick it up.
CHANNEL_LABELS: Dict[str, str] = {
    "cesr": "CESR",
    "ic1": "IC1 (Ion Chamber 1)",
    "ic2": "IC2 (Ion Chamber 2)",
    "diode": "Diode",
    "flow": "Flow Rate",
    "energy": "Energy",
    "mostab": "Mostab",
}
# "energy" now lives in CHANNEL_ORDER (per the user's explicit request to
# show it "under the same banner as Beam Condition" alongside CESR/IC1/
# IC2/Diode, rather than in its own separate row) -- _build_summary_tab()'s
# beam_row loop iterates this list and only explicitly skips "flow" (still
# shown in the Temperature Information row instead), so adding "energy"
# here is what actually moves it into the Beam Condition card row with no
# other change needed on the display side. The computed Flux readout
# (not a raw channel -- see ion_chamber_flux.py) stays in its own small
# section below Beam Condition, since it isn't a live_beam_values() entry.
# "mostab" appended at the end (after "energy") -- a brand-new card, added
# per the user's explicit request to add ID4B_CNT06_VLT as a "Mostab"
# reading in the Beam Condition row; appending (rather than inserting
# next to ic1/ic2/diode/cesr) keeps every existing card's position
# unchanged.
CHANNEL_ORDER: List[str] = ["cesr", "ic1", "ic2", "diode", "flow", "energy", "mostab"]

# Compiled once: each pattern is only allowed to match a column name where
# it isn't immediately preceded/followed by another digit. Without this, a
# plain substring check for "ic1" would also match columns like "ic10" or
# "ic11" -- a real, different, differently-numbered channel on beamlines
# that have more than 2 ion chambers -- which is exactly the kind of
# false-positive match that produces a confidently-wrong number instead of
# an honest "no match". (Reported: a real SPEC file's "ic1"/"cesr" readouts
# came out wrong while "ic2"/"diode" came out right -- consistent with an
# accidental match onto a same-prefix, different-numbered column for the
# other two.)
_COMPILED_PATTERNS: Dict[str, List["re.Pattern"]] = {
    canonical: [re.compile(r"(?<!\d)" + re.escape(pat) + r"(?!\d)") for pat in patterns]
    for canonical, patterns in CHANNEL_NAME_PATTERNS.items()
}


def match_spec_columns(columns: List[str]) -> Dict[str, Optional[str]]:
    """Match the 4 canonical channel names against a SPEC file's column
    header list, case-insensitively. Returns {canonical: actual_column_name
    or None}. Tries an exact (case-insensitive) match against each pattern
    first, then falls back to a substring match, so this works whether a
    given SPEC file's column is literally named "cesr" or something like
    "CESR_mon" -- while still preferring an exact match over a looser one
    when both are present. The substring fallback requires the pattern not
    be immediately adjacent to another digit, so "ic1" won't accidentally
    match a genuinely different channel like "ic10" or "ic11"."""
    lower_map: Dict[str, str] = {}
    for c in columns or []:
        lower_map.setdefault(c.lower(), c)

    result: Dict[str, Optional[str]] = {}
    for canonical, patterns in CHANNEL_NAME_PATTERNS.items():
        found = None
        for pat in patterns:
            if pat in lower_map:
                found = lower_map[pat]
                break
        if found is None:
            regexes = _COMPILED_PATTERNS[canonical]
            for col_lower, col_orig in lower_map.items():
                if any(rx.search(col_lower) for rx in regexes):
                    found = col_orig
                    break
        result[canonical] = found
    return result


def get_spec_live_values(
    df, columns: List[str]
) -> Dict[str, Optional[float]]:
    """Read the latest (last-row) value of each of the 4 canonical beam-
    monitor channels from a SPEC dataframe, using match_spec_columns() for
    name matching. Returns {canonical: float or None} -- None for any
    channel with no matching column, an empty/missing dataframe, or a
    non-numeric last value."""
    values: Dict[str, Optional[float]] = {c: None for c in CHANNEL_NAME_PATTERNS}
    if df is None or columns is None:
        return values
    try:
        empty = df.empty
    except AttributeError:
        return values
    if empty:
        return values

    col_map = match_spec_columns(columns)
    for canonical, col in col_map.items():
        if col is None or col not in df.columns:
            continue
        try:
            values[canonical] = float(df[col].iloc[-1])
        except (ValueError, TypeError, IndexError, KeyError):
            values[canonical] = None
    return values


# ---------------------------------------------------------------------
# Direct network polling (opt-in; requires on-site/CHESS network access)
# ---------------------------------------------------------------------

# canonical -> {pv, multiplier, range}. "range" validates the RAW value
# read back from the endpoint (before the multiplier is applied) -- for
# ic1/ic2/diode this matches the validation the user's own script performs
# (-10 to 100 V, accepting a wide swing including negative/near-zero
# readings for an off/low beam).
#
# ic1/ic2/diode are confirmed by a real script the user shared (its own
# ALL_PV_MAPPING dict). cesr's PV (ID4B_CNT01_VLT) was told to me directly
# by the user in chat -- it plausibly fits the numbering gap between IC1's
# ID4B_CNT00_VLT and IC2's ID4B_CNT02_VLT, but unlike ic1/ic2/diode it does
# NOT come from a script's own mapping dict, and I have not independently
# verified it (this sandbox can't reach signals.chess.cornell.edu or
# new-status.chess.cornell.edu to check). The multiplier for cesr is
# UNKNOWN and deliberately left at 1 (no scaling) rather than guessing
# ic1/ic2/diode's x10000 -- CESR beam current is a different kind of
# reading (mA, from new-status.chess.cornell.edu, currently ~0.01 mA)
# than the ion-chamber/diode voltages, so there's no reason to assume the
# same scale factor applies. The range below is a permissive placeholder
# (not derived from any confirmed spec) just wide enough not to reject a
# plausible reading outright. TODO once this is genuinely live: compare
# the dashboard's displayed CESR value against the reading shown on
# new-status.chess.cornell.edu/ID4B and adjust the multiplier/range here
# if they don't match.
BEAM_PV_MAP: Dict[str, Dict] = {
    "cesr": {"pv": "ID4B_CNT01_VLT", "multiplier": 1, "range": (-10, 1000)},
    "ic1": {"pv": "ID4B_CNT00_VLT", "multiplier": 10000, "range": (-10, 100)},
    "ic2": {"pv": "ID4B_CNT02_VLT", "multiplier": 10000, "range": (-10, 100)},
    "diode": {"pv": "ID4B_CNT03_VLT", "multiplier": 10000, "range": (-10, 100)},
    # No known network PV for flow -- the user's flow_get SPEC macro calls
    # a SPEC-side function (_flow_get()), not an HTTP/PV endpoint, so there
    # was nothing to wire in here without guessing. pv=None means
    # ChessSignalsClient.get_values() skips it entirely (no request made,
    # always reports None) -- same treatment CESR got before its PV was
    # known. Flow still works fine as a Summary-tab readout via the SPEC-
    # file-column path (get_spec_live_values()), since "flow" is a real
    # logged column in the sample SPEC data. Add a real pv/multiplier/range
    # here the same way CESR's was added, if one turns up.
    "flow": {"pv": None, "multiplier": 1, "range": (-10, 100)},
    # Beam energy PV -- ID4B_MON_KEV, given directly by the user in chat
    # (like CESR's PV before it). The name itself indicates the raw value
    # read back from signals.chess.cornell.edu is already in keV (the
    # monochromator energy), not a raw voltage needing ic1/ic2/diode's
    # x10000-style scaling -- so multiplier is 1, and the range (0, 200)
    # is a generous keV-scale band around ion_chamber_flux.VALID_RANGE_EV's
    # 5-100 keV working range, wide enough not to reject a plausible
    # reading. As with CESR, this PV name has not been independently
    # verified from this sandbox (still can't reach signals.chess.cornell.
    # edu here) -- worth sanity-checking the dashboard's live Energy number
    # against the actual monochromator readout once run on-site.
    "energy": {"pv": "ID4B_MON_KEV", "multiplier": 1, "range": (0, 200)},
    # "mostab" -- ID4B_CNT06_VLT, counter #6 in the same ID4B_CNTnn_VLT
    # family as ic1 (CNT00), cesr (CNT01), ic2 (CNT02), diode (CNT03). The
    # user gave this PV directly (via a signals.chess.cornell.edu/plot?
    # ...&pv=ID4B_CNT06_VLT&... URL) along with that URL's own
    # yunits=volts&ymin=0&ymax=10&ytype=linear query params, confirming the
    # RAW signal is linear volts in a 0-10V band -- but, unlike ic1/ic2/
    # diode's confirmed x10000 (from a script's own ALL_PV_MAPPING dict),
    # no engineering-unit conversion factor for "mostab" has been given, so
    # the multiplier here is left at 1 (displayed as raw volts) rather than
    # guessed at x10000 -- the same "don't assume ic1/ic2/diode's scale
    # factor transfers" judgment call already made for cesr above. The
    # range (0, 10) matches the URL's own ymin/ymax exactly (tighter than
    # the generic -10/100 placeholder used for ic1/ic2/diode, since this
    # one's band is actually confirmed by the user's URL). Sanity-check
    # the dashboard's live Mostab number on-site and update the multiplier
    # here if a real engineering-unit scale factor turns up, the same way
    # CESR's/other channels' entries would be revised.
    "mostab": {"pv": "ID4B_CNT06_VLT", "multiplier": 1, "range": (0, 10)},
}

# The cryostat temperature PVs from the user's original temperature-only
# script (ChessLiveDataExtractor/ChessBot) -- these three PV names are the
# most solidly-sourced of anything in this module: they came from that
# script AND the user separately re-typed/confirmed them directly in chat
# (ID4B_CRYOGL_STG1_T, ID4B_CRYOGL_SAM_T, ID4B_CRYOGL_STG2_T), so unlike
# CESR's PV there's no "user told me, unverified" caveat needed here. The
# multiplier is left at 1 (no scaling) since temperature readings don't
# have the ion-chamber/diode-style x10000 raw-voltage-to-reading scaling --
# and the range is a permissive placeholder wide enough to admit plausible
# Kelvin cryostat readings without rejecting real values, not a confirmed
# CHESS spec.
#
# BUGFIX (was (50, 400)): the lower bound of 50 silently rejected every
# genuine reading below 50K -- get_values() below sets a channel to None
# whenever the raw value falls outside "range", and _record_temp_history()
# in spec_dashboard_qt.py deliberately leaves a channel's plotted line
# flat/paused (not zero, not a gap) on any tick where its value is None.
# In combination, once the real cryostat temperature dropped under 50K,
# every live-network tick for that channel was silently discarded and the
# Temperature vs Time plot froze at the last accepted reading -- exactly
# the "stuck at 50K" symptom reported. The Summary strip's Y-axis is
# already fixed to the full 0-500K range (see setYRange(0, 500, ...) in
# _build_summary_tab()), so the validation range here is widened to match
# (0, 500) rather than a narrower band, so genuine readings anywhere in
# that displayable range are accepted instead of clamped/dropped.
TEMPERATURE_PV_MAP: Dict[str, Dict] = {
    "stage1": {"pv": "ID4B_CRYOGL_STG1_T", "multiplier": 1, "range": (0, 500)},
    "sample": {"pv": "ID4B_CRYOGL_SAM_T", "multiplier": 1, "range": (0, 500)},
    "stage2": {"pv": "ID4B_CRYOGL_STG2_T", "multiplier": 1, "range": (0, 500)},
}

# The Lakeshore temperature-controller SETPOINT PVs (the target
# temperature programmed into the controller, not the measured/actual
# reading -- ID4B_CRYOGL_*_T above), added per the user's explicit request
# to show the setpoint under each channel's line on the Temperature tab.
# PV names given directly by the user in chat: LAKESHORE2:SETP_S1 (Stage 1
# (A)), LAKESHORE2:SETP_S2 (Sample Temp), LAKESHORE2:SETP_S3 (Stage 2 (C)).
# Same shape as TEMPERATURE_PV_MAP/BEAM_PV_MAP (pv/multiplier/range) so it
# works with ChessSignalsClient.get_values() unchanged; multiplier 1 (no
# scaling) and range (0, 500) match TEMPERATURE_PV_MAP's own range, since a
# setpoint is a target within the same 0-500K displayable window as the
# actual reading. Setpoints are network-only (see get_live_setpoint_values()
# below) -- unlike the 3 measured-temperature channels, there's no SPEC-file
# column equivalent to fall back to, since a setpoint is a controller
# target, not scan data.
SETPOINT_PV_MAP: Dict[str, Dict] = {
    "stage1": {"pv": "LAKESHORE2:SETP_S1", "multiplier": 1, "range": (0, 500)},
    "sample": {"pv": "LAKESHORE2:SETP_S2", "multiplier": 1, "range": (0, 500)},
    "stage2": {"pv": "LAKESHORE2:SETP_S3", "multiplier": 1, "range": (0, 500)},
}

# Canonical temperature channel name -> SPEC column name patterns, mirroring
# CHANNEL_NAME_PATTERNS above but for the 3 cryostat temperature channels
# instead of the 4 beam-monitor channels. Kept as a separate dict (not
# merged into CHANNEL_NAME_PATTERNS) so beam-channel matching/behavior is
# completely unaffected by adding temperature support.
TEMPERATURE_NAME_PATTERNS: Dict[str, List[str]] = {
    "stage1": ["stage1", "stg1", "cryo_stage1", "cryo_stg1", "cryogl_stg1"],
    "sample": ["sample_t", "sample_temp", "sampletemp", "cryo_sample", "cryogl_sam"],
    "stage2": ["stage2", "stg2", "cryo_stage2", "cryo_stg2", "cryogl_stg2"],
}

TEMPERATURE_LABELS: Dict[str, str] = {
    "stage1": "Stage 1 (A)",
    "sample": "Sample Temp",
    "stage2": "Stage 2 (C)",
}
TEMPERATURE_ORDER: List[str] = ["stage1", "sample", "stage2"]

# Same digit-boundary protection as _COMPILED_PATTERNS above (e.g. so a
# "stage1" pattern can't accidentally match a differently-numbered
# "stage10" column on some other beamline's SPEC file).
_TEMP_COMPILED_PATTERNS: Dict[str, List["re.Pattern"]] = {
    canonical: [re.compile(r"(?<!\d)" + re.escape(pat) + r"(?!\d)") for pat in patterns]
    for canonical, patterns in TEMPERATURE_NAME_PATTERNS.items()
}


def match_temperature_columns(columns: List[str]) -> Dict[str, Optional[str]]:
    """Match the 3 canonical temperature channel names (stage1/sample/
    stage2) against a SPEC file's column header list. Same exact-then-
    substring, case-insensitive, digit-boundary-protected matching
    strategy as match_spec_columns() -- see that function's docstring --
    just against TEMPERATURE_NAME_PATTERNS instead of
    CHANNEL_NAME_PATTERNS."""
    lower_map: Dict[str, str] = {}
    for c in columns or []:
        lower_map.setdefault(c.lower(), c)

    result: Dict[str, Optional[str]] = {}
    for canonical, patterns in TEMPERATURE_NAME_PATTERNS.items():
        found = None
        for pat in patterns:
            if pat in lower_map:
                found = lower_map[pat]
                break
        if found is None:
            regexes = _TEMP_COMPILED_PATTERNS[canonical]
            for col_lower, col_orig in lower_map.items():
                if any(rx.search(col_lower) for rx in regexes):
                    found = col_orig
                    break
        result[canonical] = found
    return result


def get_spec_live_temperatures(df, columns: List[str]) -> Dict[str, Optional[float]]:
    """Read the latest (last-row) value of each of the 3 canonical cryostat
    temperature channels from a SPEC dataframe, using
    match_temperature_columns() for name matching. Mirrors
    get_spec_live_values() exactly, just for temperatures instead of beam-
    monitor channels. Returns {canonical: float or None}."""
    values: Dict[str, Optional[float]] = {c: None for c in TEMPERATURE_NAME_PATTERNS}
    if df is None or columns is None:
        return values
    try:
        empty = df.empty
    except AttributeError:
        return values
    if empty:
        return values

    col_map = match_temperature_columns(columns)
    for canonical, col in col_map.items():
        if col is None or col not in df.columns:
            continue
        try:
            values[canonical] = float(df[col].iloc[-1])
        except (ValueError, TypeError, IndexError, KeyError):
            values[canonical] = None
    return values


def get_live_temperature_values(
    df=None,
    columns: Optional[List[str]] = None,
    use_network: bool = False,
    client: Optional["ChessSignalsClient"] = None,
) -> Dict[str, Dict]:
    """Get the 3 live cryostat temperature values (stage1, sample, stage2).
    Same SPEC-file-first-then-network-overrides priority as
    get_live_beam_values() -- see that function's docstring for the full
    rationale (network-first when use_network=True, so toggling the
    checkbox has a visible effect even when the SPEC file already has
    matching columns). Returns the same {canonical: {"value", "source",
    "column"}} shape, just for "stage1"/"sample"/"stage2" instead of
    "cesr"/"ic1"/"ic2"/"diode"."""
    result: Dict[str, Dict] = {
        c: {"value": None, "source": None, "column": None} for c in TEMPERATURE_NAME_PATTERNS
    }

    if df is not None and columns:
        col_map = match_temperature_columns(columns)
        for c, v in get_spec_live_temperatures(df, columns).items():
            if v is not None:
                result[c] = {"value": v, "source": "spec", "column": col_map.get(c)}

    if use_network:
        active_client = client or ChessSignalsClient()
        for c, v in active_client.get_values(TEMPERATURE_PV_MAP).items():
            if v is not None:
                result[c] = {
                    "value": v,
                    "source": "network",
                    "column": TEMPERATURE_PV_MAP.get(c, {}).get("pv"),
                }

    return result


def get_live_setpoint_values(
    use_network: bool = False,
    client: Optional["ChessSignalsClient"] = None,
) -> Dict[str, Optional[float]]:
    """Get the 3 live Lakeshore temperature setpoints (stage1/sample/
    stage2) from EPICS via SETPOINT_PV_MAP. Network-only, unlike
    get_live_temperature_values() -- a setpoint is the target value
    programmed into the Lakeshore controller, not scan data, so there's no
    SPEC-file column to fall back to. Returns {canonical: float or None};
    every channel is None when use_network is False (the "Try live
    network fetch" checkbox is unchecked) or the request fails/finds
    nothing, same as every other network-sourced channel in this module.
    Deliberately returns a plain float per channel (not the {"value",
    "source", "column"} dict shape get_live_temperature_values()/
    get_live_beam_values() use) since the setpoint is display-only here --
    it's never plotted, so callers don't need to distinguish its source."""
    result: Dict[str, Optional[float]] = {c: None for c in SETPOINT_PV_MAP}
    if not use_network:
        return result
    active_client = client or ChessSignalsClient()
    for c, v in active_client.get_values(SETPOINT_PV_MAP).items():
        result[c] = v
    return result


def leading_number(text) -> Optional[float]:
    """Pull the leading numeric portion out of a PV's string value,
    ignoring any trailing unit/text -- e.g. "51.996 keV" -> 51.996, "0.0231"
    -> 0.0231, "" or None -> None. Kept here as a small standalone utility
    for spec_dashboard_qt.py's EnergyEpicsFetchThread, which calls
    `epics.caget(pv, as_string=True)` directly on a background thread (see
    that class's docstring) -- that call can come back with the PV's own
    engineering units appended (depends on the record's EGU field, e.g.
    "45.000 keV"), and needs a plain float out of it, the same shape this
    module's HTTP path (fetch_raw()) already returns."""
    if text is None:
        return None
    match = re.match(r"\s*([-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)", str(text))
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


class ChessSignalsClient:
    """Thin client for signals.chess.cornell.edu's /plot/UPDATE_{pv}
    endpoint. Only usable from a machine that can actually reach that host
    (on-site / the CHESS network) -- every request will simply fail (and
    get_values() will return None for every channel) from anywhere else,
    including this dashboard's own development/test sandbox. `requests` is
    imported lazily inside __init__ so the rest of this module (and the
    dashboard's SPEC-file-based readouts) keep working even on a machine
    where `requests` isn't installed."""

    def __init__(self, base_url: str = BASE_URL, timeout: float = 5.0, session=None):
        self.base_url = base_url
        self.timeout = timeout
        if session is not None:
            self.session = session
        else:
            import requests  # lazy import -- see docstring above

            self.session = requests.Session()
            self.session.headers.update(
                {
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Accept-Language": "en-US,en;q=0.9",
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": f"{self.base_url}/plot",
                }
            )

    def fetch_raw(self, pv_name: str) -> Optional[float]:
        """GET {base_url}/plot/UPDATE_{pv_name}. The confirmed-working
        response shape is a JSON array; the live value is the last element.
        Returns None on any error (non-200, non-JSON, empty array,
        connection failure, timeout, blocked egress, ...) -- this is
        expected/normal when called from anywhere off the CHESS network."""
        url = f"{self.base_url}/plot/UPDATE_{pv_name}"
        try:
            resp = self.session.get(url, timeout=self.timeout)
        except Exception:
            return None
        if resp.status_code != 200:
            return None
        try:
            data = resp.json()
        except ValueError:
            return None
        if isinstance(data, list) and data:
            try:
                return float(data[-1])
            except (ValueError, TypeError):
                return None
        return None

    def get_values(self, pv_map: Dict[str, Dict]) -> Dict[str, Optional[float]]:
        """Fetch + validate + scale every channel in pv_map (a dict shaped
        like BEAM_PV_MAP/TEMPERATURE_PV_MAP), all over HTTP
        (fetch_raw()/signals.chess.cornell.edu). A channel with pv=None
        (e.g. "flow", which has no known network PV) is always reported
        as None without making any request for it.

        HTTP-only, full stop -- no EPICS Channel Access here at all (see
        this module's docstring for why: a real on-site EPICS attempt in
        this codebase caused repeated caRepeater warnings and, worse, GUI
        freezes when called synchronously from the 1s Summary-tab tick).
        Live Energy over EPICS is instead handled entirely in
        spec_dashboard_qt.py, by a small dedicated one-shot background
        thread (EnergyEpicsFetchThread) that's completely independent of
        this client and this function."""
        results: Dict[str, Optional[float]] = {}
        for canonical, info in pv_map.items():
            pv = info.get("pv")
            if not pv:
                results[canonical] = None
                continue
            raw = self.fetch_raw(pv)
            if raw is None:
                results[canonical] = None
                continue
            lo, hi = info.get("range", (None, None))
            if lo is not None and hi is not None and not (lo <= raw <= hi):
                results[canonical] = None
                continue
            results[canonical] = raw * info.get("multiplier", 1)
        return results


# ---------------------------------------------------------------------
# Combined entry point used by the dashboard
# ---------------------------------------------------------------------


def get_live_beam_values(
    df=None,
    columns: Optional[List[str]] = None,
    use_network: bool = False,
    client: Optional[ChessSignalsClient] = None,
) -> Dict[str, Dict]:
    """Get the live beam-monitor values (CESR, IC1, IC2, diode, Flow).

    Priority depends on use_network:

    - use_network=False (default): only the SPEC-file column values are
      used (df/columns, if given).

    - use_network=True: for each channel, a live signals.chess.cornell.edu
      reading (ChessSignalsClient.get_values(BEAM_PV_MAP)) is preferred
      over the SPEC file's value, falling back to the SPEC-file value only
      if the network didn't provide one for that channel (no confirmed PV
      for it yet, e.g. CESR, or the request failed/is unreachable). This
      is deliberately network-first rather than SPEC-first when the
      network path is turned on: a loaded SPEC file is a static snapshot
      of its last row and generally does NOT change again once loaded
      (the app only re-reads it if the file itself changes on disk), so
      an earlier SPEC-first version of this function meant checking "Try
      live network fetch" had *no effect at all* on any channel the SPEC
      file already had a column for -- the readout would just silently
      keep showing the same frozen SPEC-file number forever, which is
      exactly the "none of the values changed" behavior a user reported
      seeing. Network-first fixes that: with the checkbox on, IC1/IC2/
      Diode should now actually update over time (once genuinely reachable
      -- this sandbox still can't reach signals.chess.cornell.edu to
      verify that end-to-end).

    Returns {canonical: {"value": float or None, "source": "spec" or
    "network" or None, "column": the matched SPEC column name or PV name
    that the value came from, or None}} for each of "cesr", "ic1", "ic2",
    "diode" -- the "column" entry is included specifically so a caller
    (e.g. the Summary tab's tooltip) can show exactly which column/PV
    produced a given number, to make a wrong match (matching the wrong
    column) obvious/diagnosable rather than just silently confidently
    wrong.
    """
    result: Dict[str, Dict] = {
        c: {"value": None, "source": None, "column": None} for c in CHANNEL_NAME_PATTERNS
    }

    if df is not None and columns:
        col_map = match_spec_columns(columns)
        for c, v in get_spec_live_values(df, columns).items():
            if v is not None:
                result[c] = {"value": v, "source": "spec", "column": col_map.get(c)}

    if use_network:
        active_client = client or ChessSignalsClient()
        # Every BEAM_PV_MAP channel, including "energy", over HTTP only --
        # see this module's docstring for why EPICS was fully backed out
        # of this function. get_live_beam_values()'s caller
        # (spec_dashboard_qt.py's _beam_signals_tick()) separately merges
        # in a live EPICS Energy reading, sourced from its own
        # EnergyEpicsFetchThread, on top of whatever this HTTP call
        # returns for "energy" (which is usually nothing -- ID4B_MON_KEV
        # has never been confirmed to answer over signals.chess.cornell.edu,
        # only over real EPICS Channel Access).
        for c, v in active_client.get_values(BEAM_PV_MAP).items():
            if v is not None:
                # Network-first: overwrite whatever the SPEC file had for
                # this channel, since the network reading is the genuinely
                # live one. Channels the network didn't provide a value for
                # (no confirmed PV, request failed, etc.) simply keep
                # whatever the SPEC-file loop above already set (or stay
                # None if that didn't match either).
                result[c] = {
                    "value": v,
                    "source": "network",
                    "column": BEAM_PV_MAP.get(c, {}).get("pv"),
                }

    return result
