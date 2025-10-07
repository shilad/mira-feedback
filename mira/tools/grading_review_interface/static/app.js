// Grading Review Interface - Main JavaScript

// Global state
const state = {
    submissions: [],
    currentSubmission: null,
    rubric: null,
    statistics: null,
    terminal: null
};

// Initialize application
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

async function initializeApp() {
    // Load initial data
    await loadSubmissions();
    await loadStatistics();
    await loadRubric();

    // Set up event listeners
    setupEventListeners();

    // Configure marked for markdown rendering
    if (typeof marked !== 'undefined') {
        marked.setOptions({
            breaks: true,
            gfm: true
        });
    }

    showToast('Application loaded successfully', 'success');
}

// Event listeners
function setupEventListeners() {
    // Header actions
    document.getElementById('save-btn').addEventListener('click', saveResults);

    // Search and filter
    document.getElementById('search-box').addEventListener('input', filterSubmissions);
    document.getElementById('filter-select').addEventListener('change', filterSubmissions);

    // Rubric button
    document.getElementById('rubric-btn')?.addEventListener('click', showRubricModal);

    // Editor actions
    document.getElementById('update-btn').addEventListener('click', updateFeedback);
    document.getElementById('next-btn').addEventListener('click', selectNextSubmission);

    // Modals
    document.getElementById('close-rubric')?.addEventListener('click', () => {
        document.getElementById('rubric-modal').classList.remove('active');
    });

    // Character counter for overall comment
    document.getElementById('overall-comment').addEventListener('input', (e) => {
        document.getElementById('comment-chars').textContent = e.target.value.length;
        autoSaveDebounced();
    });

    // File expand/collapse buttons
    document.getElementById('expand-all-btn')?.addEventListener('click', expandAllFiles);
    document.getElementById('collapse-all-btn')?.addEventListener('click', collapseAllFiles);

    // Click outside modal to close
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.remove('active');
            }
        });
    });

    // Setup keyboard shortcuts
    setupKeyboardShortcuts();
}

// Load submissions
async function loadSubmissions() {
    try {
        const response = await fetch('/api/submissions');
        const data = await response.json();

        if (data.success) {
            state.submissions = data.submissions;
            renderSubmissionsList();
        } else {
            showToast('Failed to load submissions: ' + data.error, 'error');
        }
    } catch (error) {
        showToast('Error loading submissions: ' + error.message, 'error');
    }
}

// Render submissions list
function renderSubmissionsList() {
    const container = document.getElementById('submissions-list');

    if (state.submissions.length === 0) {
        container.innerHTML = '<div class="loading">No submissions found</div>';
        return;
    }

    container.innerHTML = state.submissions.map(sub => {
        const edited = sub.edited ? '<span class="badge badge-edited">Edited</span>' : '';
        const scorePercent = ((sub.total_score / sub.max_score) * 100).toFixed(0);

        return `
            <div class="submission-item" data-student-id="${sub.student_id}" onclick="selectSubmission('${sub.student_id}')">
                <div class="name">${sub.student_id}</div>
                <div class="score">
                    <span>${sub.total_score}/${sub.max_score} (${scorePercent}%)</span>
                    ${edited}
                </div>
            </div>
        `;
    }).join('');
}

// Filter submissions
function filterSubmissions() {
    const searchTerm = document.getElementById('search-box').value.toLowerCase();
    const filterType = document.getElementById('filter-select').value;

    let filtered = state.submissions;

    // Apply search filter
    if (searchTerm) {
        filtered = filtered.filter(sub =>
            sub.student_id.toLowerCase().includes(searchTerm)
        );
    }

    // Apply type filter
    if (filterType !== 'all') {
        filtered = filtered.filter(sub => {
            switch (filterType) {
                case 'edited':
                    return sub.edited;
                case 'unedited':
                    return !sub.edited;
                case 'low-score':
                    return (sub.total_score / sub.max_score) < 0.7;
                default:
                    return true;
            }
        });
    }

    // Render filtered list
    const container = document.getElementById('submissions-list');
    container.innerHTML = filtered.map(sub => {
        const edited = sub.edited ? '<span class="badge badge-edited">Edited</span>' : '';
        const scorePercent = ((sub.total_score / sub.max_score) * 100).toFixed(0);

        return `
            <div class="submission-item" data-student-id="${sub.student_id}" onclick="selectSubmission('${sub.student_id}')">
                <div class="name">${sub.student_id}</div>
                <div class="score">
                    <span>${sub.total_score}/${sub.max_score} (${scorePercent}%)</span>
                    ${edited}
                </div>
            </div>
        `;
    }).join('');
}

// Select submission
async function selectSubmission(studentId) {
    try {
        const response = await fetch(`/api/submissions/${encodeURIComponent(studentId)}`);
        const data = await response.json();

        if (data.success) {
            state.currentSubmission = data.submission;
            renderSubmissionEditor();

            // Update active state in list
            document.querySelectorAll('.submission-item').forEach(item => {
                item.classList.remove('active');
                if (item.dataset.studentId === studentId) {
                    item.classList.add('active');
                }
            });

            // Load files list
            loadSubmissionFiles(studentId);
        } else {
            showToast('Failed to load submission: ' + data.error, 'error');
        }
    } catch (error) {
        showToast('Error loading submission: ' + error.message, 'error');
    }
}

// Render submission editor
function renderSubmissionEditor() {
    const sub = state.currentSubmission;

    // Show editor, hide no-selection message
    document.getElementById('no-selection').style.display = 'none';
    document.getElementById('editor-content').style.display = 'flex';

    // Update header
    document.getElementById('student-name').textContent = sub.student_id;
    document.getElementById('current-score').textContent = sub.total_score;
    document.getElementById('max-score').textContent = sub.max_score;

    // Update overall comment
    const commentTextarea = document.getElementById('overall-comment');
    commentTextarea.value = sub.comment || '';
    document.getElementById('comment-chars').textContent = commentTextarea.value.length;

    // Render components with adjustments
    const componentsContainer = document.getElementById('components-container');
    componentsContainer.innerHTML = Object.entries(sub.components || {}).map(([name, comp]) => {
        // Calculate if score matches adjustments
        const expectedScore = calculateExpectedScore(comp);
        // Filter out zero-point adjustments
        const nonZeroAdjustments = (comp.adjustments || []).filter(a => a.score_impact !== 0);
        const llmAdjustments = nonZeroAdjustments.filter(a => !a.is_manual);
        const manualAdjustments = nonZeroAdjustments.filter(a => a.is_manual);
        const hasLLMAdjustments = llmAdjustments.length > 0;

        return `
        <div class="component-card" data-component="${name}">
            <div class="component-header-line">
                <span class="component-name">${name}:</span>
                <div class="component-feedback-inline"
                     contenteditable="true"
                     data-component="${name}"
                     onblur="updateComponentFeedback('${name}', this.textContent)">${comp.feedback || 'Add feedback...'}</div>
                <div class="component-score-inline">
                    <span class="score-display" data-component="${name}">${comp.score.toFixed(1)}</span>
                    <span class="score-max">/ ${comp.max_score}</span>
                </div>
            </div>

            <div class="adjustments-container">
                <div class="adjustments-list">
                    ${renderAdjustments(name, llmAdjustments, 'llm')}
                    ${renderAdjustments(name, manualAdjustments, 'manual')}
                    <button class="add-adjustment-btn" onclick="addManualAdjustment('${name}')">add adjustment</button>
                </div>
            </div>
        </div>
    `;
    }).join('');
}

// Calculate expected score from adjustments
function calculateExpectedScore(comp) {
    if (!comp.adjustments || comp.adjustments.length === 0) {
        return comp.max_score;
    }

    const totalImpact = comp.adjustments.reduce((sum, adj) => sum + (adj.score_impact || 0), 0);
    return Math.max(0, Math.min(comp.max_score, comp.max_score + totalImpact));
}

// Render adjustments in single-line format with edit/remove buttons
function renderAdjustments(componentName, adjustments, type = 'llm') {
    if (!adjustments || adjustments.length === 0) {
        return '';
    }

    return adjustments.map((adj, index) => {
        const impactClass = adj.score_impact < 0 ? 'negative' :
                           adj.score_impact > 0 ? 'positive' : 'neutral';
        const uniqueId = `${componentName}-${type}-${index}`;

        return `
        <div class="adjustment-item-line" data-component="${componentName}" data-type="${type}" data-index="${index}" id="adj-${uniqueId}">
            <input class="adj-name-input" type="text" value="${adj.name || 'unnamed'}"
                   onchange="updateAdjustmentField('${componentName}', ${index}, '${type}', 'name', this.value)"
                   placeholder="Name">
            <input class="adj-desc-input" type="text" value="${adj.description || ''}"
                   onchange="updateAdjustmentField('${componentName}', ${index}, '${type}', 'description', this.value)"
                   placeholder="Description">
            <input class="adj-score-input ${impactClass}" type="number" value="${adj.score_impact}" step="0.25"
                   onchange="updateAdjustmentField('${componentName}', ${index}, '${type}', 'score_impact', this.value)">
            <button class="adj-btn-remove" onclick="removeAdjustmentQuick('${componentName}', ${index}, '${type}')" title="Remove">×</button>
        </div>
    `;
    }).join('');
}

// Removed toggleAdjustments - no longer needed since adjustments are always expanded

// Component scores and feedback are now updated only via adjustments

// Add manual adjustment
function addManualAdjustment(componentName) {
    const comp = state.currentSubmission.components[componentName];

    if (!comp.adjustments) {
        comp.adjustments = [];
    }

    const newAdjustment = {
        name: 'manual-adjustment',
        description: 'Manual score adjustment',
        score_impact: 0,
        is_manual: true
    };

    comp.adjustments.push(newAdjustment);

    // Re-render the component
    renderSubmissionEditor();

    // Show toast
    showToast('Added manual adjustment. Edit the values as needed.', 'info');
}

// Clear all adjustments - removed since we now allow individual removal

// Update total score display
function updateTotalScore() {
    let totalScore = 0;
    Object.values(state.currentSubmission.components || {}).forEach(comp => {
        totalScore += comp.score || 0;
    });

    state.currentSubmission.total_score = totalScore;

    // Update the display
    const currentScoreElem = document.getElementById('current-score');
    if (currentScoreElem) {
        currentScoreElem.textContent = totalScore.toFixed(1);
    }

    // Also update in the submissions list
    const submissionItem = document.querySelector(`.submission-item[data-student-id="${state.currentSubmission.student_id}"] .score span`);
    if (submissionItem) {
        const maxScore = state.currentSubmission.max_score;
        const percent = ((totalScore / maxScore) * 100).toFixed(0);
        submissionItem.textContent = `${totalScore.toFixed(1)}/${maxScore} (${percent}%)`;
    }
}

// Add a new adjustment
function addAdjustment(componentName) {
    const comp = state.currentSubmission.components[componentName];
    const newAdjustment = {
        name: 'new-adjustment',
        description: 'Enter description here',
        score_impact: 0
    };

    if (!comp.adjustments) {
        comp.adjustments = [];
    }
    comp.adjustments.push(newAdjustment);

    // Re-render adjustments list
    document.getElementById(`adjustments-${componentName}`).innerHTML =
        renderAdjustments(componentName, comp.adjustments);

    // Re-render to show the new adjustment
    renderSubmissionEditor();
}

// Update a single adjustment field inline
function updateAdjustmentField(componentName, index, type, field, value) {
    const comp = state.currentSubmission.components[componentName];
    if (!comp || !comp.adjustments) return;

    const adjType = type === 'llm' ? false : true;
    const adjustments = comp.adjustments.filter(a => (a.is_manual || false) === adjType);
    const adj = adjustments[index];

    if (!adj) return;

    // Update the field
    if (field === 'score_impact') {
        adj[field] = parseFloat(value) || 0;
        // Update input class based on new value
        const input = document.querySelector(`#adj-${componentName}-${type}-${index} .adj-score-input`);
        if (input) {
            input.className = 'adj-score-input ' +
                (adj.score_impact < 0 ? 'negative' : adj.score_impact > 0 ? 'positive' : 'neutral');
        }
    } else {
        adj[field] = value;
    }

    // Recalculate scores automatically
    recalculateComponentScore(componentName);
    updateTotalScore();
    autoSaveDebounced();
}

// Save edited adjustment
function saveAdjustment(componentName, index) {
    const comp = state.currentSubmission.components[componentName];
    const adj = comp.adjustments[index];

    // Update adjustment data
    adj.name = document.getElementById(`adj-name-${componentName}-${index}`).value;
    adj.description = document.getElementById(`adj-desc-${componentName}-${index}`).value;
    adj.score_impact = parseFloat(document.getElementById(`adj-score-${componentName}-${index}`).value) || 0;

    // Re-render adjustments list
    document.getElementById(`adjustments-${componentName}`).innerHTML =
        renderAdjustments(componentName, comp.adjustments);

    // Recalculate score based on adjustments
    recalculateScore(componentName);
}

// Cancel editing adjustment
function cancelEditAdjustment(componentName, index) {
    const comp = state.currentSubmission.components[componentName];

    // Re-render adjustments list without changes
    document.getElementById(`adjustments-${componentName}`).innerHTML =
        renderAdjustments(componentName, comp.adjustments);
}

// Remove an adjustment without confirmation
function removeAdjustmentQuick(componentName, index, type) {
    const comp = state.currentSubmission.components[componentName];
    const allAdjustments = comp.adjustments || [];
    const adjType = type === 'llm' ? false : true;
    const adjustments = allAdjustments.filter(a => (a.is_manual || false) === adjType);

    if (adjustments[index]) {
        const adjToRemove = adjustments[index];
        const realIndex = allAdjustments.indexOf(adjToRemove);
        if (realIndex !== -1) {
            allAdjustments.splice(realIndex, 1);
        }
    }

    // Re-render and recalculate
    renderSubmissionEditor();
    recalculateComponentScore(componentName);
    updateTotalScore();
    autoSaveDebounced();
}

// Update component feedback
function updateComponentFeedback(componentName, newFeedback) {
    const comp = state.currentSubmission.components[componentName];
    if (!comp) return;

    // Handle empty or "Add feedback..." placeholder
    if (newFeedback === 'Add feedback...' || newFeedback.trim() === '') {
        comp.feedback = '';
    } else {
        comp.feedback = newFeedback.trim();
    }

    // Mark as edited
    state.currentSubmission.edited = true;
    updateSubmissionDisplay();

    // Auto-save with debouncing
    clearTimeout(autoSaveTimer);
    autoSaveTimer = setTimeout(() => {
        saveFeedbackSilent();
    }, 1000);
}

// Recalculate component score based on adjustments
function recalculateComponentScore(componentName) {
    const comp = state.currentSubmission.components[componentName];
    if (!comp) return;

    // Calculate score from adjustments
    let totalImpact = 0;
    if (comp.adjustments && comp.adjustments.length > 0) {
        totalImpact = comp.adjustments.reduce((sum, adj) => sum + (adj.score_impact || 0), 0);
    }

    // Base score is max_score + total impact
    const calculatedScore = Math.max(0, Math.min(comp.max_score, comp.max_score + totalImpact));

    // Update score in state
    comp.score = calculatedScore;

    // Update score display in UI
    const scoreDisplay = document.querySelector(`.score-display[data-component="${componentName}"]`);
    if (scoreDisplay) {
        scoreDisplay.textContent = calculatedScore.toFixed(1);
    }

    // Don't auto-generate feedback - it's now independently editable
}

// Update total score
function updateTotalScore() {
    let totalScore = 0;
    Object.values(state.currentSubmission.components).forEach(comp => {
        totalScore += comp.score || 0;
    });

    state.currentSubmission.total_score = totalScore;
    document.getElementById('current-score').textContent = totalScore;
}


// Select next submission
function selectNextSubmission() {
    const currentId = state.currentSubmission?.student_id;
    if (!currentId) return;

    const currentIndex = state.submissions.findIndex(s => s.student_id === currentId);
    if (currentIndex < state.submissions.length - 1) {
        selectSubmission(state.submissions[currentIndex + 1].student_id);
    } else {
        showToast('This is the last submission', 'info');
    }
}

// Load submission files
async function loadSubmissionFiles(studentId) {
    try {
        const response = await fetch(`/api/submissions/${encodeURIComponent(studentId)}/files`);
        const data = await response.json();

        if (data.success) {
            // Store files data for later use
            state.currentFiles = data.files;

            // Load file contents for all files
            await loadAllFileContents(studentId, data.files);

            // Render the files list with content
            renderFilesList(data.files);
        } else {
            showToast('Failed to load files: ' + data.error, 'error');
        }
    } catch (error) {
        showToast('Error loading files: ' + error.message, 'error');
    }
}

// Load all file contents
async function loadAllFileContents(studentId, files) {
    const fileContents = {};
    let totalLines = 0;

    // Load all file contents in parallel
    const promises = files.map(async (file) => {
        try {
            const response = await fetch(`/api/submissions/${encodeURIComponent(studentId)}/files/${encodeURIComponent(file.path)}`);
            const data = await response.json();

            if (data.success) {
                const lines = data.content.split('\n');
                fileContents[file.path] = {
                    content: data.content,
                    lineCount: lines.length
                };
                totalLines += lines.length;
            }
        } catch (error) {
            console.error(`Error loading file ${file.path}:`, error);
            fileContents[file.path] = {
                content: 'Error loading file',
                lineCount: 0
            };
        }
    });

    await Promise.all(promises);

    // Store file contents and total lines
    state.fileContents = fileContents;
    state.totalFileLines = totalLines;
}

// Render files list with expandable content
function renderFilesList(files) {
    const container = document.getElementById('files-list');

    if (files.length === 0) {
        container.innerHTML = '<p class="loading">No files found</p>';
        return;
    }

    // Determine if files should be auto-expanded
    const shouldAutoExpand = state.totalFileLines < 500;

    container.innerHTML = files.map((file, index) => {
        const sizeKB = (file.size / 1024).toFixed(1);
        const fileContent = state.fileContents[file.path];
        const lineCount = fileContent ? fileContent.lineCount : 0;
        const isExpanded = shouldAutoExpand;

        // Get file extension for icon
        const ext = file.path.split('.').pop().toLowerCase();
        const icon = getFileIcon(ext);

        return `
            <div class="file-item-expandable" data-file-path="${file.path}" data-expanded="${isExpanded}">
                <div class="file-header" onclick="toggleFileExpansion('${file.path}')">
                    <div class="file-info">
                        <i class="fas fa-chevron-${isExpanded ? 'down' : 'right'} file-toggle"></i>
                        <i class="fas ${icon}"></i>
                        <span class="file-name">${file.path}</span>
                        <span class="file-meta">${lineCount} lines • ${sizeKB} KB</span>
                    </div>
                </div>
                <div class="file-content-wrapper" style="display: ${isExpanded ? 'block' : 'none'}">
                    <div class="file-content">
                        <pre><code class="hljs language-${ext}">${escapeHtml(fileContent?.content || '')}</code></pre>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    // Apply syntax highlighting to all expanded files
    if (typeof hljs !== 'undefined') {
        container.querySelectorAll('pre code').forEach(block => {
            hljs.highlightElement(block);
        });
    }

    // Update expand/collapse buttons
    updateExpandCollapseButtons();
}

// Toggle file expansion
function toggleFileExpansion(filePath) {
    const fileItem = document.querySelector(`.file-item-expandable[data-file-path="${filePath}"]`);
    if (!fileItem) return;

    const isExpanded = fileItem.dataset.expanded === 'true';
    const newExpanded = !isExpanded;

    // Update UI
    fileItem.dataset.expanded = newExpanded;
    const toggle = fileItem.querySelector('.file-toggle');
    toggle.className = `fas fa-chevron-${newExpanded ? 'down' : 'right'} file-toggle`;

    const contentWrapper = fileItem.querySelector('.file-content-wrapper');
    contentWrapper.style.display = newExpanded ? 'block' : 'none';

    // Apply syntax highlighting when expanding
    if (newExpanded && typeof hljs !== 'undefined') {
        const codeBlock = contentWrapper.querySelector('code');
        if (codeBlock && !codeBlock.classList.contains('hljs')) {
            hljs.highlightElement(codeBlock);
        }
    }

    updateExpandCollapseButtons();
}

// Expand all files
function expandAllFiles() {
    document.querySelectorAll('.file-item-expandable').forEach(item => {
        item.dataset.expanded = 'true';
        item.querySelector('.file-toggle').className = 'fas fa-chevron-down file-toggle';
        item.querySelector('.file-content-wrapper').style.display = 'block';
    });

    // Apply syntax highlighting
    if (typeof hljs !== 'undefined') {
        document.querySelectorAll('.file-content-wrapper code').forEach(block => {
            if (!block.classList.contains('hljs')) {
                hljs.highlightElement(block);
            }
        });
    }

    updateExpandCollapseButtons();
}

// Collapse all files
function collapseAllFiles() {
    document.querySelectorAll('.file-item-expandable').forEach(item => {
        item.dataset.expanded = 'false';
        item.querySelector('.file-toggle').className = 'fas fa-chevron-right file-toggle';
        item.querySelector('.file-content-wrapper').style.display = 'none';
    });

    updateExpandCollapseButtons();
}

// Update expand/collapse button states
function updateExpandCollapseButtons() {
    const allItems = document.querySelectorAll('.file-item-expandable');
    const expandedItems = document.querySelectorAll('.file-item-expandable[data-expanded="true"]');

    const expandBtn = document.getElementById('expand-all-btn');
    const collapseBtn = document.getElementById('collapse-all-btn');

    if (expandBtn && collapseBtn) {
        expandBtn.disabled = allItems.length === expandedItems.length;
        collapseBtn.disabled = expandedItems.length === 0;
    }
}

// Get file icon based on extension
function getFileIcon(ext) {
    const iconMap = {
        'py': 'fa-python',
        'js': 'fa-js',
        'java': 'fa-java',
        'cpp': 'fa-code',
        'c': 'fa-code',
        'html': 'fa-html5',
        'css': 'fa-css3',
        'json': 'fa-file-code',
        'xml': 'fa-file-code',
        'md': 'fa-markdown',
        'txt': 'fa-file-alt',
        'pdf': 'fa-file-pdf',
        'zip': 'fa-file-archive',
        'png': 'fa-file-image',
        'jpg': 'fa-file-image',
        'jpeg': 'fa-file-image',
        'gif': 'fa-file-image'
    };

    return iconMap[ext] || 'fa-file-code';
}

// Escape HTML for safe display
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Load rubric
async function loadRubric() {
    try {
        const response = await fetch('/api/rubric');
        const data = await response.json();

        if (data.success) {
            state.rubric = data.rubric;
            renderRubric();
        }
    } catch (error) {
        console.error('Error loading rubric:', error);
    }
}

// Render rubric
function renderRubric() {
    if (!state.rubric) return;

    const container = document.getElementById('rubric-content');
    if (typeof marked !== 'undefined') {
        container.innerHTML = marked.parse(state.rubric);
    } else {
        container.innerHTML = `<pre>${state.rubric}</pre>`;
    }
}

// Show rubric modal
function showRubricModal() {
    if (!state.rubric) {
        loadRubric().then(() => {
            renderRubric();
            document.getElementById('rubric-modal').classList.add('active');
        });
    } else {
        renderRubric();
        document.getElementById('rubric-modal').classList.add('active');
    }
}

// Load statistics
async function loadStatistics() {
    try {
        const response = await fetch('/api/statistics');
        const data = await response.json();

        if (data.success) {
            state.statistics = data.statistics;
            renderStatistics();
        }
    } catch (error) {
        console.error('Error loading statistics:', error);
    }
}

// Render statistics
function renderStatistics() {
    const stats = state.statistics;
    if (!stats) return;

    // Update header stats
    document.getElementById('stat-total-inline').textContent = stats.total_submissions || 0;
    document.getElementById('stat-avg-inline').textContent =
        stats.average_score ? stats.average_score.toFixed(2) : '-';
    document.getElementById('stat-edited-inline').textContent = stats.edited_count || 0;

    if (stats.score_distribution) {
        const dist = stats.score_distribution;
        document.getElementById('stat-range-inline').textContent =
            `${dist.min}-${dist.max}`;
    }
}

// Show detailed statistics
function showDetailedStats() {
    const stats = state.statistics;
    if (!stats) return;

    const modal = document.getElementById('stats-modal');
    const container = document.getElementById('detailed-stats');

    const dist = stats.score_distribution || {};

    container.innerHTML = `
        <div class="stats-grid">
            <h4>Overall Statistics</h4>
            <table style="width: 100%; margin: 1rem 0;">
                <tr>
                    <td><strong>Total Submissions:</strong></td>
                    <td>${stats.total_submissions || 0}</td>
                </tr>
                <tr>
                    <td><strong>Successful:</strong></td>
                    <td>${stats.successful || 0}</td>
                </tr>
                <tr>
                    <td><strong>Failed:</strong></td>
                    <td>${stats.failed || 0}</td>
                </tr>
                <tr>
                    <td><strong>Edited:</strong></td>
                    <td>${stats.edited_count || 0}</td>
                </tr>
            </table>

            <h4>Score Distribution</h4>
            <table style="width: 100%; margin: 1rem 0;">
                <tr>
                    <td><strong>Average:</strong></td>
                    <td>${stats.average_score ? stats.average_score.toFixed(2) : '-'}</td>
                </tr>
                <tr>
                    <td><strong>Minimum:</strong></td>
                    <td>${dist.min || '-'}</td>
                </tr>
                <tr>
                    <td><strong>Maximum:</strong></td>
                    <td>${dist.max || '-'}</td>
                </tr>
                <tr>
                    <td><strong>Median:</strong></td>
                    <td>${dist.median || '-'}</td>
                </tr>
                <tr>
                    <td><strong>Max Possible:</strong></td>
                    <td>${dist.max_possible || '-'}</td>
                </tr>
            </table>
        </div>
    `;

    modal.classList.add('active');
}

// Save results
async function saveResults() {
    try {
        const response = await fetch('/api/save', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ backup: true })
        });

        const data = await response.json();

        if (data.success) {
            showToast('Results saved successfully', 'success');
        } else {
            showToast('Failed to save results: ' + data.error, 'error');
        }
    } catch (error) {
        showToast('Error saving results: ' + error.message, 'error');
    }
}

// Export results
async function exportResults() {
    try {
        window.location.href = '/api/export';
        showToast('Downloading results...', 'info');
    } catch (error) {
        showToast('Error exporting results: ' + error.message, 'error');
    }
}

// Show terminal
function showTerminal() {
    const modal = document.getElementById('terminal-modal');
    modal.classList.add('active');

    // Initialize terminal if not already done
    if (!state.terminal && typeof Terminal !== 'undefined') {
        state.terminal = new Terminal({
            cursorBlink: true,
            theme: {
                background: '#1e1e1e',
                foreground: '#d4d4d4'
            }
        });

        const container = document.getElementById('terminal');
        state.terminal.open(container);

        state.terminal.writeln('Terminal ready. This is a demonstration terminal.');
        state.terminal.writeln('To run grading commands, use your system terminal.');
        state.terminal.writeln('');
        state.terminal.writeln('Example commands:');
        state.terminal.writeln('  grade-batch -s ./2_redacted -r rubric.md');
        state.terminal.writeln('  grade-submission --submission-dir ./2_redacted/STUDENT_NAME -r rubric.md');
    }
}

// Re-grade selected submission
function regradeSelected() {
    const studentId = state.currentSubmission?.student_id;
    if (!studentId) {
        showToast('No submission selected', 'warning');
        return;
    }

    showToast('Re-grading functionality requires running grade-submission from terminal', 'info');
    showTerminal();
}

// Re-grade all submissions
function regradeAll() {
    showToast('Re-grading all functionality requires running grade-batch from terminal', 'info');
    showTerminal();
}

// Show toast notification
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icon = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    }[type] || 'fa-info-circle';

    toast.innerHTML = `
        <i class="fas ${icon}"></i>
        <span>${message}</span>
    `;

    container.appendChild(toast);

    // Auto-remove after 4 seconds
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// Setup keyboard shortcuts
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ignore if user is typing in an input field
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            // Allow Escape key even in input fields
            if (e.key === 'Escape') {
                e.target.blur();
                return;
            }
            return;
        }

        // Keyboard shortcuts
        switch(e.key) {
            case 'ArrowDown':
            case 'j':
                selectNextSubmission();
                e.preventDefault();
                break;
            case 'ArrowUp':
            case 'k':
                selectPreviousSubmission();
                e.preventDefault();
                break;
            case 'Enter':
                if (e.ctrlKey || e.metaKey) {
                    updateFeedback();
                    e.preventDefault();
                }
                break;
            case 's':
                if (e.ctrlKey || e.metaKey) {
                    e.preventDefault();
                    saveResults();
                }
                break;
            case '1':
                switchTab('feedback');
                break;
            case '2':
                switchTab('files');
                break;
            case '3':
                switchTab('rubric');
                break;
            case '/':
                e.preventDefault();
                document.getElementById('search-box').focus();
                break;
            case 'Escape':
                // Close any open modals
                document.querySelectorAll('.modal.active').forEach(modal => {
                    modal.classList.remove('active');
                });
                closeFileViewer();
                break;
            case '?':
                if (e.shiftKey) {
                    showKeyboardHelp();
                }
                break;
        }
    });
}

// Select previous submission
function selectPreviousSubmission() {
    if (!state.currentSubmission) return;

    const currentIndex = state.submissions.findIndex(
        s => s.student_id === state.currentSubmission.student_id
    );

    if (currentIndex > 0) {
        selectSubmission(state.submissions[currentIndex - 1].student_id);
    }
}

// Show keyboard help modal
function showKeyboardHelp() {
    const helpContent = `
        <div style="padding: 1rem;">
            <h3>Keyboard Shortcuts</h3>
            <table style="width: 100%; margin-top: 1rem;">
                <tr><td><kbd>j</kbd> or <kbd>↓</kbd></td><td>Next submission</td></tr>
                <tr><td><kbd>k</kbd> or <kbd>↑</kbd></td><td>Previous submission</td></tr>
                <tr><td><kbd>Ctrl/Cmd + Enter</kbd></td><td>Update feedback</td></tr>
                <tr><td><kbd>Ctrl/Cmd + S</kbd></td><td>Save results</td></tr>
                <tr><td><kbd>1</kbd></td><td>Feedback tab</td></tr>
                <tr><td><kbd>2</kbd></td><td>Files tab</td></tr>
                <tr><td><kbd>3</kbd></td><td>Rubric tab</td></tr>
                <tr><td><kbd>/</kbd></td><td>Focus search</td></tr>
                <tr><td><kbd>Esc</kbd></td><td>Close modal/viewer</td></tr>
                <tr><td><kbd>?</kbd></td><td>Show this help</td></tr>
            </table>
        </div>
    `;

    // Create and show modal
    const modal = document.createElement('div');
    modal.className = 'modal active';
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h3><i class="fas fa-keyboard"></i> Keyboard Shortcuts</h3>
                <button class="close-modal" onclick="this.closest('.modal').remove()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            ${helpContent}
        </div>
    `;
    document.body.appendChild(modal);

    // Close on click outside
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.remove();
        }
    });
}

// Auto-save functionality
let autoSaveTimer = null;
const AUTOSAVE_DELAY = 2000; // 2 seconds

function autoSaveDebounced() {
    if (!state.currentSubmission) return;

    // Clear existing timer
    if (autoSaveTimer) {
        clearTimeout(autoSaveTimer);
    }

    // Show saving indicator
    const saveBtn = document.getElementById('save-btn');
    const originalText = saveBtn.innerHTML;
    saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Auto-saving...';
    saveBtn.disabled = true;

    // Set new timer
    autoSaveTimer = setTimeout(async () => {
        await updateFeedback(true); // Pass true for auto-save
        saveBtn.innerHTML = originalText;
        saveBtn.disabled = false;
        showToast('Auto-saved', 'success');
    }, AUTOSAVE_DELAY);
}

// Update the updateFeedback function to support auto-save
async function updateFeedback(isAutoSave = false) {
    if (!state.currentSubmission) return;

    const overallComment = document.getElementById('overall-comment').value;
    const components = {};

    // Collect component data from the new structure
    document.querySelectorAll('.component-card').forEach(card => {
        const componentName = card.dataset.component;
        const scoreInput = card.querySelector('.component-score-input');
        const feedbackTextarea = card.querySelector('.component-feedback');

        if (componentName && state.currentSubmission.components[componentName]) {
            const comp = state.currentSubmission.components[componentName];
            components[componentName] = {
                score: parseFloat(scoreInput?.value) || comp.score || 0,
                max_score: comp.max_score,
                feedback: feedbackTextarea?.value || comp.feedback || '',
                adjustments: comp.adjustments || []
            };
        }
    });

    const data = {
        student_id: state.currentSubmission.student_id,
        overall_comment: overallComment,
        components: components,
        total_score: Object.values(components).reduce((sum, c) => sum + c.score, 0)
    };

    try {
        const response = await fetch(`/api/submissions/${encodeURIComponent(data.student_id)}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (result.success) {
            state.currentSubmission.comment = overallComment;
            state.currentSubmission.components = components;
            state.currentSubmission.edited = true;
            state.currentSubmission.total_score = data.total_score;

            // Update submission in list
            const subIndex = state.submissions.findIndex(s => s.student_id === data.student_id);
            if (subIndex !== -1) {
                state.submissions[subIndex].edited = true;
                state.submissions[subIndex].total_score = data.total_score;
            }

            renderSubmissionsList();

            if (!isAutoSave) {
                showToast('Feedback updated successfully', 'success');
            }
        } else {
            showToast('Failed to update feedback: ' + result.error, 'error');
        }
    } catch (error) {
        showToast('Error updating feedback: ' + error.message, 'error');
    }
}

// Removed preview functions - no longer needed
