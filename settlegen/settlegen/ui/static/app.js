document.addEventListener('DOMContentLoaded', () => {
    const terrainFeatures = [
        "plain", "forest", "dense_forest", "hill", "mountain_pass", 
        "river", "stream", "lakeside", "bay", "coast", "island", 
        "swamp", "marsh", "delta", "cliff", "desert_edge", 
        "oasis", "fertile_valley", "volcanic"
    ];

    const facilities = [
        "city_hall", "keep", "castle", "stone_wall", "palisade", "tower",
        "market", "inn", "tavern", "guildhall", "bank",
        "temple", "church", "monastery", "cemetery", "library",
        "mage_tower", "runestone_circle", "blacksmith", "forge",
        "bridge", "docks", "lighthouse", "watermill", "farmstead",
        "house", "manor", "ruin"
    ];

    const terrainContainer = document.getElementById('terrain-container');
    const facilitiesContainer = document.getElementById('facilities-container');

    function createCheckboxes(items, container, name) {
        items.forEach(item => {
            const label = document.createElement('label');
            label.className = 'checkbox-label';
            const input = document.createElement('input');
            input.type = 'checkbox';
            input.name = name;
            input.value = item;
            
            // default selections
            if (name === 'terrain' && item === 'plain') input.checked = true;

            const text = document.createTextNode(item.replace(/_/g, ' '));
            
            label.appendChild(input);
            label.appendChild(text);
            container.appendChild(label);
        });
    }

    createCheckboxes(terrainFeatures, terrainContainer, 'terrain');
    createCheckboxes(facilities, facilitiesContainer, 'facilities');

    const form = document.getElementById('config-form');
    const btn = document.getElementById('generate-btn');
    const outName = document.getElementById('out-name');
    const outPop = document.getElementById('out-pop');
    const outBuildings = document.getElementById('out-buildings');
    const outDistricts = document.getElementById('out-districts');
    const asciiMap = document.getElementById('ascii-map');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        btn.classList.add('loading');
        btn.disabled = true;

        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());
        
        // Handle multiples (checkboxes)
        data.terrain = formData.getAll('terrain');
        data.facilities = formData.getAll('facilities');

        // Convert ints
        data.seed = parseInt(data.seed);
        data.width = parseInt(data.width);
        data.height = parseInt(data.height);

        try {
            const res = await fetch('/api/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });

            if (!res.ok) throw new Error('Generation failed');
            
            const result = await res.json();
            
            outName.textContent = result.name;
            outPop.textContent = result.population.toLocaleString();
            outBuildings.textContent = result.buildings_count.toLocaleString();
            outDistricts.textContent = result.districts_count.toLocaleString();
            
            asciiMap.textContent = result.map;

        } catch (err) {
            alert('Error generating settlement: ' + err.message);
        } finally {
            btn.classList.remove('loading');
            btn.disabled = false;
        }
    });
});
