window.dash_clientside = Object.assign({}, window.dash_clientside, {
    clientside: {
        update_map_canvas: function(arcData, baseMapDict, perspective, selectedCountry) {
            if (!baseMapDict) {
                return window.dash_clientside.no_update;
            }

            // Select the appropriate base map based on the perspective toggle
            if (perspective === 'attacker') {
                var baseMapString = baseMapDict.attacker;
            } else if (perspective === 'receiver') {
                var baseMapString = baseMapDict.receiver;
            }
            
            // Convert the base map string back to a JSON object
            let deckData = JSON.parse(baseMapString);

            // Only update arcs once the perspective and selected country are defined
            if (perspective && selectedCountry) {
                const arcLayer = {
                    "id": 'arc-layer',
                    "@@type": 'ArcLayer',
                    "pickable": true,
                    "data": arcData[perspective][selectedCountry],
                    "getSourcePosition": "@@=[origin_lon, origin_lat]",
                    "getTargetPosition": "@@=[dest_lon, dest_lat]",
                    "getSourceColor": [205, 0, 0, 255],
                    "getTargetColor": [0, 0, 205, 255],
                    "autoHighlight": true,
                    "highlightColor": [255, 255, 255, 128],
                    "getWidth": 6,
                    "getTilt": 15,
                    "widthMinPixels": 2,
                };
                deckData.layers.push(arcLayer);
            }
            return JSON.stringify(deckData);
        }
    }
});

function attachIncidentModalBackdropHandler() {
    const overlay = document.querySelector('.incident-info-modal-overlay');
    if (!overlay || overlay.dataset.backdropHandlerAttached === 'true') {
        return;
    }

    overlay.dataset.backdropHandlerAttached = 'true';
    overlay.addEventListener('click', function (event) {
        if (event.target !== overlay) {
            return;
        }

        if (window.dash_clientside && window.dash_clientside.set_props) {
            window.dash_clientside.set_props('large-incident-modal', {
                children: [],
                style: { display: 'none' },
            });
        }
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', attachIncidentModalBackdropHandler);
} else {
    attachIncidentModalBackdropHandler();
}

const modalObserver = new MutationObserver(function () {
    attachIncidentModalBackdropHandler();
});
modalObserver.observe(document.body, { childList: true, subtree: true });