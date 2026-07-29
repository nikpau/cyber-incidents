document.addEventListener('contextmenu', function(event) {
    // Find the map container using the ID we assigned in Python.
    const mapCanvas = document.getElementById('map-container');
    const inspectorCard = document.getElementById('floating-inspector-card')
        || document.querySelector('.floating-inspector-card');

    // Prevent the browser context menu when the user right-clicks inside the map
    // or the inspector card.
    if ((mapCanvas && mapCanvas.contains(event.target)) ||
        (inspectorCard && inspectorCard.contains(event.target))) {
        event.preventDefault();
    }
});