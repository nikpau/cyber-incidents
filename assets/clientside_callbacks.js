window.dash_clientside = Object.assign({}, window.dash_clientside, {
    clientside: {
        update_map_canvas: function(arcData, baseMapString) {
            if (!baseMapString) {
                return window.dash_clientside.no_update;
            }
            
            // Convert the base map string back to a JSON object
            let deckData = JSON.parse(baseMapString);

            // If the server sent us arcs, update the deckData with them
            if (arcData && arcData.length > 0) {
                const arcLayer = {
                    "id": 'arc-layer',
                    "@@type": 'ArcLayer',
                    "pickable": true,
                    "data": arcData,
                    "getSourcePosition": "@@=[origin_lon, origin_lat]",
                    "getTargetPosition": "@@=[dest_lon, dest_lat]",
                    "getSourceColor": [205, 0, 0, 255],
                    "getTargetColor": [0, 0, 205, 255],
                    "autoHighlight": true,
                    "highlightColor": [255, 255, 255, 128],
                    "getWidth": 4,
                    "getTilt": 15,
                    "widthMinPixels": 2,
                };
                deckData.layers.push(arcLayer);
            }
            return JSON.stringify(deckData);
        }
    }
});