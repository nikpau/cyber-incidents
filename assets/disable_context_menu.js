document.addEventListener('contextmenu', function(event) {
    // Find the map container using the ID we assigned in Python
    const mapCanvas = document.getElementById('map-container');
    
    // If the user right-clicked somewhere inside the map, prevent the menu
    if (mapCanvas && mapCanvas.contains(event.target)) {
        event.preventDefault();
    }
});