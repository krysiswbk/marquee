"""Contracts for the household activity remainder disclosure."""

from pathlib import Path

ROOT = Path(__file__).parents[1]
BRAIN = (ROOT / "output" / "brain.js").read_text()
STYLES = (ROOT / "output" / "brain.css").read_text()


def test_activity_disclosure_uses_the_authoritative_fresh_event_list() -> None:
    assert "const opening=fresh" in BRAIN
    assert "const now=Date.now()/1000, fresh=state.fresh&&now-received<45" in BRAIN
    assert "const eventRows=events.slice(0,3)" in BRAIN
    assert 'aria-label="View all ${events.length} recent events"' in BRAIN
    assert "renderActivity(events, fresh)" in BRAIN


def test_activity_states_are_truthful_without_fallback_events() -> None:
    assert "No new door or lock activity in the last 15 minutes." in BRAIN
    assert "Activity feed reconnecting; recent activity is unavailable." in BRAIN
    assert "Activity is unavailable while the household feed is offline." in BRAIN
    assert "No recent activity is recorded." in BRAIN
    assert "if(!events.length)return" in BRAIN
    assert "events.map(e=>" in BRAIN


def test_activity_lifecycle_supports_close_escape_history_and_focus_return() -> None:
    for token in (
        'role="dialog"',
        'aria-modal="true"',
        "history.pushState({marqueeActivity:true}",
        "history.back()",
        "event.key==='Escape'",
        "focusTarget.focus()",
        "window.addEventListener('popstate'",
        "setActivityBackground(true)",
        "event.key!=='Tab'",
        "reconcileActivityHash(events, fresh)",
        "activityFallback=$('brain-headline')",
        "const activityBackgroundState=new Map()",
        "prior.ariaHidden===null",
        "prior.inert)node.setAttribute('inert','')",
        "fromHistory?activityFallback",
        "!activityReturnTarget.matches('[inert]')",
    ):
        assert token in BRAIN
    assert "setTimeout(()=>closeActivity(true),0)" not in BRAIN
    assert "setTimeout(()=>{if(destination.isConnected" not in BRAIN
    assert "requestAnimationFrame(()=>{const focusTarget=(returnFocusId==='brain-activity-open'&&$('brain-activity-open'))" in BRAIN
    assert "marquee-history-focus-owned" in BRAIN


def test_activity_history_focus_claims_are_scoped_to_real_traversals() -> None:
    assert "activityHistoryTraversalPending=false" in BRAIN
    assert "activityHistoryState=false;activityHistoryTraversalPending=true;window.dispatchEvent(new Event('marquee-history-focus-owned'));history.back()" in BRAIN
    assert "if(activityHistoryTraversalPending)activityHistoryTraversalPending=false;else window.dispatchEvent(new Event('marquee-history-focus-owned'));closeActivity(true)" in BRAIN
    assert "window.dispatchEvent(new Event('marquee-history-focus-owned'));\n    if(activityHistoryState" not in BRAIN


def test_activity_controls_and_records_are_touch_and_responsive() -> None:
    assert ".brain-event-more button{min-height:44px" in STYLES
    assert ".brain-activity-dialog button{min-width:44px;min-height:44px" in STYLES
    assert "max-height:62vh;overflow:auto" in STYLES
    assert "grid-template-columns:minmax(0,1fr) minmax(0,auto)" in STYLES
    assert ".brain-activity-record time,.brain-activity-record strong,.brain-activity-record span{min-width:0;overflow-wrap:anywhere}" in STYLES
    assert "@media(max-width:600px)" in STYLES
    assert 'role="region" aria-label="Recent activity records; use arrow keys or scroll to review" tabindex="0"' in BRAIN
