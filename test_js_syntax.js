// Test JavaScript syntax from template
// This is extracted from templates/index.html

async function startWatchMode() {
    const watchStatusDiv = document.getElementById('watchStatus');
    const statusSpan = document.getElementById('watchModeStatus');
    
    watchStatusDiv.style.display = 'block';
    statusSpan.textContent = 'Starting...';
    
    try {
        const response = await fetch('/api/watch/start');
        if (response.ok) {
            statusSpan.textContent = 'Running';
        } else {
            const error = await response.json();
            alert('❌ Failed to start watch mode: ' + (error.detail || 'Unknown error'));
            watchStatusDiv.style.display = 'none';
        }
    } catch (error) {
        alert('❌ Error: ' + error.message);
        watchStatusDiv.style.display = 'none';
    }
}

async function stopWatchMode() {
    const watchStatusDiv = document.getElementById('watchStatus');
    const statusSpan = document.getElementById('watchModeStatus');
    
    try {
        const response = await fetch('/api/watch/stop');
        if (response.ok) {
            statusSpan.textContent = 'Stopped';
            setTimeout(() => {
                watchStatusDiv.style.display = 'none';
            }, 2000);
        } else {
            const error = await response.json();
            alert('❌ Failed to stop watch mode: ' + (error.detail || 'Unknown error'));
            watchStatusDiv.style.display = 'none';
        }
    } catch (error) {
        alert('❌ Error: ' + error.message);
        watchStatusDiv.style.display = 'none';
    }
}

// If this runs without errors, syntax is correct
console.log('JavaScript syntax check: ✅ PASS');
