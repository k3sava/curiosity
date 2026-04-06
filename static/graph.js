/* curiosity — D3.js space-cluster knowledge graph */

(function() {
  const container = document.getElementById('graph-canvas');
  if (!container) return;

  const width = container.clientWidth;
  const height = container.clientHeight || 600;
  const tooltip = document.getElementById('graph-tooltip');

  async function loadGraph() {
    const resp = await fetch('/api/graph');
    const data = await resp.json();
    render(data);
  }

  function render(data) {
    container.innerHTML = '';

    if (!data.nodes.length) {
      container.innerHTML = '<div class="empty-state"><p>No spaces to display</p></div>';
      return;
    }

    const svg = d3.select(container)
      .append('svg')
      .attr('width', width)
      .attr('height', height);

    const g = svg.append('g');

    // Zoom
    const zoom = d3.zoom()
      .scaleExtent([0.3, 3])
      .on('zoom', (event) => g.attr('transform', event.transform));
    svg.call(zoom);

    // Scale node size by count
    const maxCount = Math.max(...data.nodes.map(n => n.count));
    const sizeScale = d3.scaleSqrt().domain([0, maxCount]).range([20, 60]);

    // Simulation
    const simulation = d3.forceSimulation(data.nodes)
      .force('link', d3.forceLink(data.edges).id(d => d.id)
        .distance(d => 180 - d.strength * 60)
        .strength(d => 0.2 + d.strength * 0.6))
      .force('charge', d3.forceManyBody().strength(-400))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(d => sizeScale(d.count) + 15));

    // Edges
    const link = g.append('g')
      .selectAll('line')
      .data(data.edges)
      .join('line')
      .attr('stroke', 'var(--border, #ddd)')
      .attr('stroke-width', d => 1 + d.shared * 0.5)
      .attr('stroke-opacity', d => 0.3 + d.strength * 0.5);

    // Node groups
    const node = g.append('g')
      .selectAll('g')
      .data(data.nodes)
      .join('g')
      .style('cursor', 'pointer')
      .call(d3.drag()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended));

    // Circles
    node.append('circle')
      .attr('r', d => sizeScale(d.count))
      .attr('fill', d => d.color)
      .attr('fill-opacity', 0.15)
      .attr('stroke', d => d.color)
      .attr('stroke-width', 2);

    // Icons
    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'central')
      .attr('font-size', d => Math.max(14, sizeScale(d.count) * 0.5))
      .attr('fill', d => d.color)
      .text(d => d.icon);

    // Labels below
    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', d => sizeScale(d.count) + 14)
      .attr('font-size', 11)
      .attr('font-weight', 500)
      .attr('fill', 'var(--text-muted, #666)')
      .text(d => d.id);

    // Count label
    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', d => sizeScale(d.count) + 26)
      .attr('font-size', 10)
      .attr('fill', 'var(--text-muted, #999)')
      .text(d => d.count + ' items');

    // Hover
    node.on('mouseover', function(event, d) {
      if (tooltip) {
        const [x, y] = d3.pointer(event, svg.node());
        tooltip.style.display = 'block';
        tooltip.style.left = (x + 16) + 'px';
        tooltip.style.top = (y - 8) + 'px';
        let html = '<strong>' + escHtml(d.id) + '</strong> (' + d.count + ')<br>';
        if (d.top_items) {
          d.top_items.forEach(function(t) {
            html += '<span style="color:var(--text-muted,#888)">' + escHtml(t.substring(0, 50)) + '</span><br>';
          });
        }
        tooltip.innerHTML = html;
      }
      d3.select(this).select('circle')
        .attr('fill-opacity', 0.3)
        .attr('stroke-width', 3);
    })
    .on('mouseout', function() {
      if (tooltip) tooltip.style.display = 'none';
      d3.select(this).select('circle')
        .attr('fill-opacity', 0.15)
        .attr('stroke-width', 2);
    })
    .on('click', function(event, d) {
      window.location.href = '/space/' + encodeURIComponent(d.id);
    });

    // Tick
    simulation.on('tick', function() {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);
      node.attr('transform', d => 'translate(' + d.x + ',' + d.y + ')');
    });

    function dragstarted(event) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      event.subject.fx = event.subject.x;
      event.subject.fy = event.subject.y;
    }

    function dragged(event) {
      event.subject.fx = event.x;
      event.subject.fy = event.y;
    }

    function dragended(event) {
      if (!event.active) simulation.alphaTarget(0);
      event.subject.fx = null;
      event.subject.fy = null;
    }
  }

  function escHtml(s) {
    var div = document.createElement('div');
    div.textContent = s || '';
    return div.innerHTML;
  }

  loadGraph();
})();
