/* ============================================================
   Our Watchlist
   Reads data/shows.json and renders it. All editing happens in
   scripts/watchlist.py - this file only ever displays.
   ============================================================ */

const DATA_URL = 'data/shows.json';

// Mirrors VERDICTS in scripts/watchlist.py - keep the two in step.
const VERDICTS = [
    [9.0, 'loved'],
    [7.5, 'great'],
    [6.0, 'liked'],
    [4.0, 'fine'],
    [0.0, 'disliked'],
];

const STATUS_LABELS = {
    finished: 'Finished',
    watching: 'Watching now',
    paused: 'Paused',
    abandoned: 'Bailed on',
};

const state = {
    viewers: {},
    shows: [],
    search: '',
    status: 'all',
    sort: 'rating',
};

/* ---------- derived values ---------- */

function scoresOf(show) {
    return Object.values(show.ratings || {}).filter((v) => typeof v === 'number');
}

function averageOf(show) {
    const vals = scoresOf(show);
    if (!vals.length) return null;
    return Math.round((vals.reduce((a, b) => a + b, 0) / vals.length) * 100) / 100;
}

function spreadOf(show) {
    const vals = scoresOf(show);
    if (vals.length < 2) return null;
    return Math.round((Math.max(...vals) - Math.min(...vals)) * 100) / 100;
}

function verdictOf(show) {
    if (show.status === 'abandoned') return 'bailed';
    const avg = averageOf(show);
    if (avg === null) return 'unrated';
    for (const [threshold, label] of VERDICTS) {
        if (avg >= threshold) return label;
    }
    return 'disliked';
}

function hoursOf(show) {
    const tmdb = show.tmdb || {};
    if (!tmdb.episodes || !tmdb.runtime) return 0;
    return (tmdb.episodes * tmdb.runtime) / 60;
}

/* ---------- summary tiles ---------- */

function renderTiles() {
    const row = document.getElementById('tileRow');
    const shows = state.shows;
    const totalHours = shows.reduce((sum, s) => sum + hoursOf(s), 0);
    const bothLoved = shows.filter((s) => {
        const vals = scoresOf(s);
        return vals.length > 1 && Math.min(...vals) >= 8;
    });
    const bailed = shows.filter((s) => s.status === 'abandoned');

    const splits = shows
        .filter((s) => spreadOf(s) !== null)
        .sort((a, b) => spreadOf(b) - spreadOf(a));
    const widest = splits[0];

    const tiles = [
        {
            label: 'Shows together',
            value: shows.length,
            sub: `${shows.filter((s) => s.status === 'finished').length} finished`,
        },
        {
            label: 'Hours watched',
            value: totalHours ? Math.round(totalHours).toLocaleString() : '—',
            sub: totalHours ? `${(totalHours / 24).toFixed(1)} solid days` : 'Run enrich for counts',
        },
        {
            label: 'You both loved',
            value: bothLoved.length,
            sub: 'Scored 8+ by each of you',
        },
        {
            label: 'Biggest split',
            value: widest ? `${spreadOf(widest)} pts` : '—',
            sub: widest ? widest.title : 'No disagreements yet',
        },
        {
            label: 'Bailed on',
            value: bailed.length,
            sub: bailed.length ? 'Worth remembering why' : 'You finish what you start',
        },
    ];

    row.innerHTML = tiles
        .map(
            (t) => `
        <div class="tile">
            <span class="tile-label">${escapeHtml(t.label)}</span>
            <span class="tile-value">${escapeHtml(String(t.value))}</span>
            <span class="tile-sub">${escapeHtml(t.sub)}</span>
        </div>`
        )
        .join('');
    row.hidden = false;
}

/* ---------- genre chart ----------
   One series, magnitude read off bar length, every bar direct-labelled
   with its value, so no legend and no colour coding are needed.        */

function renderGenres() {
    const section = document.getElementById('genreSection');
    const chart = document.getElementById('genreChart');
    const note = document.getElementById('genreNote');

    const buckets = new Map();
    state.shows.forEach((show) => {
        const avg = averageOf(show);
        if (avg === null) return;
        ((show.tmdb || {}).genres || []).forEach((genre) => {
            if (!buckets.has(genre)) buckets.set(genre, []);
            buckets.get(genre).push(avg);
        });
    });

    const ranked = [...buckets.entries()]
        .filter(([, vals]) => vals.length >= 2)
        .map(([genre, vals]) => ({
            genre,
            avg: vals.reduce((a, b) => a + b, 0) / vals.length,
            count: vals.length,
        }))
        .sort((a, b) => b.avg - a.avg);

    if (!ranked.length) {
        section.hidden = true;
        return;
    }

    chart.innerHTML = ranked
        .map((row) => {
            const pct = (row.avg / 10) * 100;
            const noun = row.count === 1 ? 'show' : 'shows';
            return `
        <div class="genre-row" title="${escapeHtml(row.genre)}: ${row.avg.toFixed(2)} average across ${row.count} ${noun}">
            <span class="genre-name">${escapeHtml(row.genre)}</span>
            <div class="genre-track"><div class="genre-bar" style="width:${pct.toFixed(1)}%"></div></div>
            <span class="genre-value">${row.avg.toFixed(1)}</span>
        </div>`;
        })
        .join('');

    const best = ranked[0];
    const worst = ranked[ranked.length - 1];
    note.textContent =
        ranked.length > 1
            ? `Your safest bet is ${best.genre} (${best.avg.toFixed(1)} average). ` +
              `${worst.genre} keeps letting you down at ${worst.avg.toFixed(1)}.`
            : `So far ${best.genre} is the only genre you've watched more than once.`;
    section.hidden = false;
}

/* ---------- show cards ---------- */

function matchesFilters(show) {
    if (state.status !== 'all' && show.status !== state.status) return false;
    if (!state.search) return true;

    const haystack = [
        show.title,
        show.note || '',
        ...(show.tags || []),
        ...((show.tmdb || {}).genres || []),
        ...((show.tmdb || {}).networks || []),
    ]
        .join(' ')
        .toLowerCase();
    return haystack.includes(state.search);
}

function sortShows(shows) {
    const sorted = [...shows];
    if (state.sort === 'rating') {
        sorted.sort((a, b) => (averageOf(b) ?? -1) - (averageOf(a) ?? -1));
    } else if (state.sort === 'spread') {
        sorted.sort((a, b) => (spreadOf(b) ?? -1) - (spreadOf(a) ?? -1));
    } else if (state.sort === 'year') {
        sorted.sort((a, b) => ((b.tmdb || {}).year || 0) - ((a.tmdb || {}).year || 0));
    } else {
        sorted.sort((a, b) => a.title.localeCompare(b.title));
    }
    return sorted;
}

function renderCards() {
    const grid = document.getElementById('showGrid');
    const visible = sortShows(state.shows.filter(matchesFilters));

    if (!visible.length) {
        grid.innerHTML =
            '<p class="tile-sub">Nothing matches that filter.</p>';
        return;
    }

    grid.innerHTML = visible.map(cardMarkup).join('');
}

function cardMarkup(show) {
    const tmdb = show.tmdb || {};
    const verdict = verdictOf(show);

    const poster = tmdb.poster
        ? `<img class="poster" src="${escapeHtml(tmdb.poster)}" alt="${escapeHtml(show.title)} poster" loading="lazy">`
        : '<div class="poster-fallback">📺</div>';

    const chips = Object.keys(state.viewers)
        .map((vid) => {
            const score = show.ratings ? show.ratings[vid] : null;
            const name = state.viewers[vid].name || vid;
            const value = typeof score === 'number' ? score : '—';
            return `<span class="chip">
                        <span class="chip-dot viewer-${escapeHtml(vid)}"></span>
                        ${escapeHtml(name)}
                        <span class="chip-score">${escapeHtml(String(value))}</span>
                    </span>`;
        })
        .join('');

    const metaBits = [
        tmdb.year,
        (tmdb.networks || [])[0],
        tmdb.seasons ? `${tmdb.seasons} season${tmdb.seasons === 1 ? '' : 's'}` : null,
        STATUS_LABELS[show.status],
    ].filter(Boolean);

    const genres = (tmdb.genres || [])
        .map((g) => `<span class="genre-tag">${escapeHtml(g)}</span>`)
        .join('');

    return `
    <article class="show-card">
        ${poster}
        <div class="show-body">
            <h3 class="show-title">${escapeHtml(show.title)}</h3>
            <p class="show-meta">${escapeHtml(metaBits.join(' · '))}</p>
            <div class="rating-chips">${chips}</div>
            <span class="badge ${escapeHtml(verdict)}">${escapeHtml(verdict)}</span>
            ${show.note ? `<p class="show-note">“${escapeHtml(show.note)}”</p>` : ''}
            <div class="genre-tags">${genres}</div>
        </div>
    </article>`;
}

/* ---------- plumbing ---------- */

function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (char) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
    })[char]);
}

function wireControls() {
    document.getElementById('showSearch').addEventListener('input', (event) => {
        state.search = event.target.value.trim().toLowerCase();
        renderCards();
    });
    document.getElementById('statusFilter').addEventListener('change', (event) => {
        state.status = event.target.value;
        renderCards();
    });
    document.getElementById('sortBy').addEventListener('change', (event) => {
        state.sort = event.target.value;
        renderCards();
    });
}

async function init() {
    let data;
    try {
        const response = await fetch(DATA_URL, { cache: 'no-store' });
        if (!response.ok) throw new Error(response.statusText);
        data = await response.json();
    } catch (error) {
        document.getElementById('showGrid').innerHTML =
            `<p class="tile-sub">Couldn't load ${DATA_URL}: ${escapeHtml(error.message)}</p>`;
        return;
    }

    state.viewers = data.viewers || {};
    state.shows = data.shows || [];

    const stamp = document.getElementById('lastUpdated');
    stamp.textContent = data.lastUpdated
        ? `Updated ${new Date(data.lastUpdated).toLocaleDateString()}`
        : '';

    if (!state.shows.length) {
        document.getElementById('emptyState').hidden = false;
        return;
    }

    document.getElementById('controls').hidden = false;
    renderTiles();
    renderGenres();
    renderCards();
    wireControls();
}

document.addEventListener('DOMContentLoaded', init);
