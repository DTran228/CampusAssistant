'use strict';
const $ = selector => document.querySelector(selector);
const csrf = $('meta[name="csrf-token"]').content;
let currentQuery = null;
let contextRevision = 0;
let savedPlans = [];
const selected = new Map();
function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
}
function status(text, error = false) {
  $('#status').textContent = text;
  $('#status').classList.toggle('error', error);
}
async function api(path, {method = 'GET', body, download = false} = {}) {
  const headers = {'X-CSRF-Token': csrf};
  if (body && !(body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(body);
  }
  const response = await fetch(path, {method, headers, body});
  if (!response.ok) {
    const result = await response.json();
    throw new Error(`${result.error?.code || response.status}: ${result.error?.message || 'Request failed'}`);
  }
  if (download) {
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = node('a'); link.href = url; link.download = 'campus-events.ics';
    document.body.append(link); link.click(); link.remove(); URL.revokeObjectURL(url);
    status('Calendar file exported. Import it into your calendar; attendance has not been registered.');
    return;
  }
  return response.json();
}
function action(button, callback) {
  button.addEventListener('click', async () => {
    button.disabled = true;
    try { await callback(); } catch (error) { status(error.message, true); }
    finally { button.disabled = false; }
  });
}
function handleForm(form, callback) {
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true; status('Working…');
    try { await callback(new FormData(form)); } catch (error) { status(error.message, true); }
    finally { button.disabled = false; }
  });
}
function sourceLink(url, label) {
  const link = node('a', label);
  if (/^https?:\/\//i.test(url)) { link.href = url; link.target = '_blank'; link.rel = 'noopener noreferrer'; }
  else { link.textContent = `${label}: ${url}`; }
  return link;
}
function eventTime(event) {
  const format = new Intl.DateTimeFormat('en-US', {month:'short', day:'numeric', hour:'numeric', minute:'2-digit', timeZone:event.timezone, timeZoneName:'short'});
  return `${format.format(new Date(event.start))} to ${format.format(new Date(event.end))}`;
}
function eventCard(event, selectable = false) {
  const card = node('article', undefined, 'card event-card');
  const tags = node('div', undefined, 'event-tags');
  for (const category of event.categories || []) tags.append(node('span', category, 'tag'));
  const freshness = node('span', event.freshness, 'tag state'); freshness.setAttribute('role', 'status'); tags.append(freshness);
  card.append(node('h3', event.title), node('p', eventTime(event), 'event-time'), tags, node('p', event.description, 'event-description'));
  const basics = node('div', undefined, 'event-basics');
  basics.append(node('span', event.location || 'Location unknown', 'meta'), node('span', `Cost: ${event.cost === null ? 'unknown' : '$' + event.cost}`, 'meta'), sourceLink(event.source_url, 'View source'));
  card.append(basics);
  const details = node('details', undefined, 'event-details');
  const facts = node('div');
  details.append(node('summary', 'Event details and source'), facts);
  facts.append(node('p', `Organizer: ${event.organizer || 'unknown'}.`, 'meta'));
  facts.append(node('p', `Free food: ${event.free_food}. Dietary information: ${event.dietary}.`, 'meta'));
  facts.append(node('p', `Revision ${event.revision}. Retrieved ${event.retrieved_at}.`, 'meta'));
  if (event.explanation) facts.append(node('p', event.explanation, 'explanation'));
  card.append(details);
  if (selectable) {
    const label = node('label', undefined, 'check');
    const checkbox = node('input'); checkbox.type = 'checkbox';
    checkbox.addEventListener('change', () => {
      if (checkbox.checked && selected.size === 5) { checkbox.checked = false; status('Choose at most five events.', true); return; }
      if (checkbox.checked) selected.set(event.id, {event_id:event.id, revision:event.revision});
      else selected.delete(event.id);
      $('#selection-count').textContent = `${selected.size} selected. Conflicts between selections are checked when saving or exporting.`;
    });
    label.append(checkbox, node('span', 'Add to selection')); card.append(label);
  }
  return card;
}
async function loadCalendars() {
  const result = await api('/api/calendars');
  if ($('#calendar-select')) {
    for (const calendar of result.calendars) {
      const option = node('option', `${calendar.intervals} busy intervals, through ${calendar.horizon_end.slice(0,10)}`);
      option.value = calendar.id; $('#calendar-select').append(option);
    }
  }
  if ($('#calendar-list')) {
    $('#calendar-list').replaceChildren();
    if (!result.calendars.length) $('#calendar-list').append(node('div', 'No availability uploaded. Import an .ics file above to check your schedule.', 'empty'));
    for (const calendar of result.calendars) {
      const card = node('article', undefined, 'card');
      card.append(node('h3', `${calendar.intervals} busy intervals`), node('p', `${calendar.horizon_start} to ${calendar.horizon_end}`, 'meta'), node('p', calendar.timezone, 'meta'));
      const button = node('button', 'Delete availability', 'secondary danger'); button.type = 'button';
      action(button, async () => { await api(`/api/calendars/${calendar.id}`, {method:'DELETE'}); status('Availability deleted. Saved plans that used it need review.'); await loadCalendars(); });
      card.append(button); $('#calendar-list').append(card);
    }
  }
}
async function loadEvents(formData) {
  const body = Object.fromEntries(formData);
  body.interests = body.interests.split(',').map(s => s.trim()).filter(Boolean);
  body.max_cost = body.max_cost === '' ? null : Number(body.max_cost);
  body.buffer_minutes = Number(body.buffer_minutes);
  body.free_food = formData.has('free_food'); body.calendar_ref ||= null;
  const result = await api('/api/recommend', {method:'POST', body});
  currentQuery = result.query; selected.clear();
  $('#selection-count').textContent = 'Choose up to 5 events. Selected events are checked against each other.';
  $('#event-results').replaceChildren();
  for (const event of result.events) $('#event-results').append(eventCard(event, true));
  if (!result.events.length) $('#event-results').append(node('div', `No event fits these constraints. ${result.relaxations.join('. ')}. Constraints have not been changed.`, 'empty'));
  $('#result-summary').textContent = `Showing ${result.events.length} of ${result.feasible_count} feasible options. Ranked by interest matches, then time. ${currentQuery.calendar_ref ? 'Availability checked.' : 'Upload availability to check class conflicts.'}`;
  $('#excluded').replaceChildren();
  for (const event of result.excluded) $('#excluded').append(node('p', `${event.title}: ${event.reasons.join(', ').replaceAll('_',' ')}`));
  if (!result.excluded.length) $('#excluded').append(node('p', 'No exclusions.'));
  status('Event search complete. Sources refresh only through the local CLI.');
}
async function loadPlans() {
  const [result, shared] = await Promise.all([api('/api/plans'), api('/api/planning-context')]);
  savedPlans = result.plans;
  contextRevision = shared.revision;
  const context = shared.context;
  $('#shared-context').replaceChildren(node('p', context ? context.summary : 'No shared context. An assistant on this profile will see an empty state.'));
  if (context) {
    $('#shared-context').append(node('p', `Interests: ${context.preferences.join(', ') || 'none'}`), node('p', `Context revision ${shared.revision}. Updated ${context.updated_at}.`, 'meta'));
    const linked = savedPlans.find(p => p.plan_ref === context.plan_ref);
    for (const event of linked?.items || []) $('#shared-context').append(node('p', `${event.title}. Current time: ${eventTime(event)}. Saved version ${event.saved_revision}.`, 'meta'));
  }
  $('#clear-context').disabled = !context;
  const form = $('#context-form');
  form.hidden = !savedPlans.length;
  form.elements.summary.value = context?.summary || '';
  form.elements.preferences.value = context?.preferences.join(', ') || '';
  form.elements.reviewed.checked = false;
  $('#context-plan').replaceChildren();
  for (const [index, plan] of savedPlans.entries()) {
    const option = node('option', `Plan ${index + 1}: ${plan.items.map(e => e.title).join(', ')}`);
    option.value = plan.plan_ref; $('#context-plan').append(option);
  }
  if (context) $('#context-plan').value = context.plan_ref;
  previewContextSelection(!context);
  $('#plan-list').replaceChildren();
  if (!result.plans.length) $('#plan-list').append(node('div', 'Your plan is empty. Explore events, choose a selection, and save it here.', 'empty'));
  for (const plan of result.plans) {
    const card = node('article', undefined, 'card');
    const state = node('span', plan.valid ? 'Current selection valid' : 'Review required', 'tag state'); state.setAttribute('role', 'status');
    card.append(node('h2', 'Saved campus plan'), state);
    for (const event of plan.items) {
      card.append(node('h3', event.title), node('p', eventTime(event), 'event-time'), node('p', `Saved revision ${event.saved_revision}. Current revision ${event.revision}. Status: ${event.status}.`, 'meta'), sourceLink(event.source_url, 'View source'));
    }
    if (plan.changes.length) {
      const list = node('ul', undefined, 'warning');
      for (const change of plan.changes) {
        let text = change.explanation || change.reason.replaceAll('_',' ');
        if (change.previous_start) text += ` Previous: ${change.previous_start} to ${change.previous_end}. Current: ${change.current_start} to ${change.current_end}.`;
        list.append(node('li', text));
      }
      card.append(list);
    }
    const controls = node('div', undefined, 'form-bottom');
    const exportButton = node('button', 'Export plan (.ics)'); exportButton.type = 'button'; exportButton.disabled = !plan.valid;
    action(exportButton, () => api(`/api/plans/${plan.plan_ref}/export`, {method:'POST', download:true}));
    const deleteButton = node('button', 'Delete plan', 'secondary danger'); deleteButton.type = 'button';
    action(deleteButton, async () => { await api(`/api/plans/${plan.plan_ref}`, {method:'DELETE'}); await loadPlans(); status('Plan deleted.'); });
    controls.append(exportButton, deleteButton); card.append(controls);
    if (!plan.valid && plan.alternatives.length) {
      card.append(node('h3', 'Alternatives to review'));
      for (const event of plan.alternatives) card.append(node('p', `${event.title}. ${eventTime(event)}. ${event.explanation}`, 'meta'));
      const link = node('a', 'Explore events to create a new selection'); link.href = '/events'; card.append(link);
    }
    $('#plan-list').append(card);
  }
}
function previewContextSelection(usePlanInterests = false) {
  const plan = savedPlans.find(p => p.plan_ref === $('#context-plan').value);
  $('#context-selection').textContent = plan ? plan.items.map(e => `${e.title}\nCurrent time: ${eventTime(e)}\nSaved version ${e.saved_revision}. Current version ${e.revision}.`).join('\n\n') : '';
  if (usePlanInterests && plan) $('#context-form').elements.preferences.value = plan.request.query.interests.join(', ');
  $('#context-form').elements.reviewed.checked = false;
}
async function init() {
  const view = document.body.dataset.view;
  if (view === 'events') {
    await loadCalendars();
    handleForm($('#event-form'), loadEvents);
    await loadEvents(new FormData($('#event-form')));
    action($('#save-selection'), async () => {
      if (!selected.size) throw new Error('Select at least one event.');
      await api('/api/plans', {method:'POST', body:{query:currentQuery, selections:[...selected.values()]}});
      status('Selection saved. Open My plan to recheck and export.');
    });
    action($('#export-selection'), async () => {
      if (!selected.size) throw new Error('Select at least one event.');
      await api('/api/export', {method:'POST', body:{query:currentQuery, selections:[...selected.values()]}, download:true});
    });
  } else if (view === 'ask') {
    handleForm($('#search-form'), async data => {
      const body = Object.fromEntries(data); body.category ||= null;
      const result = await api('/api/search', {method:'POST', body});
      $('#answer').textContent = result.answer;
      $('#evidence').replaceChildren();
      for (const item of result.excerpts) {
        const card = node('article', undefined, 'card');
        card.append(node('h2', item.title), node('span', `${item.evidence_id}, page ${item.page}`, 'tag'), node('p', item.text), sourceLink(item.url, 'Inspect source'), node('p', `Indexed ${result.indexed_at}. ${result.freshness}. Backend: ${result.backend}.`, 'meta'));
        $('#evidence').append(card);
      }
      status(result.notice);
    });
  } else if (view === 'availability') {
    await loadCalendars();
    handleForm($('#calendar-form'), async data => { const result = await api('/api/calendars', {method:'POST', body:data}); status(`${result.intervals} busy intervals stored. ${result.notice}`); await loadCalendars(); });
    action($('#pair-button'), async () => { const result = await api('/api/pair', {method:'POST'}); $('#pair-code').textContent = `One-use code: ${result.token}`; status(result.notice); });
  } else if (view === 'plan') {
    await loadPlans();
    $('#context-plan').addEventListener('change', () => previewContextSelection(true));
    $('#context-form').addEventListener('input', event => { if (event.target.name !== 'reviewed') $('#context-form').elements.reviewed.checked = false; });
    handleForm($('#context-form'), async data => {
      const body = {summary:data.get('summary'), preferences:data.get('preferences').split(',').map(s => s.trim()).filter(Boolean), plan_ref:data.get('plan_ref'), reviewed:data.has('reviewed'), expected_revision:contextRevision};
      await api('/api/planning-context', {method:'POST', body});
      await loadPlans(); status('Approved context saved. A fresh paired assistant can resume it without a plan code.');
    });
    action($('#clear-context'), async () => {
      await api('/api/planning-context', {method:'DELETE', body:{expected_revision:contextRevision}});
      await loadPlans(); status('Shared context cleared. Your original plans and availability remain.');
    });
    action($('#refresh-plans'), async () => { await loadPlans(); status('Saved selections revalidated against current source revisions.'); });
  }
}
init().catch(error => status(error.message, true));
