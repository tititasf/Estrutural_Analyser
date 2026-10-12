/* One renderer for granular SA fichas and the preprocessing structural map. */
(function () {
  'use strict';
  var NS = 'http://www.w3.org/2000/svg';
  window.StructuralSections = {
    draw: function (doc, parent, drawings, toSvg, options) {
      options = options || {};
      (drawings || []).forEach(function (drawing) {
        var group = doc.createElementNS(NS, 'g');
        group.setAttribute('class', 'lv-structural-section');
        group.setAttribute('data-cut-index', drawing.cut_index == null ? '' : drawing.cut_index);
        (drawing.primitives || []).forEach(function (item) {
          if (item.kind === 'text' && item.size === 8 && options.names === false) return;
          var pts = item.points.map(toSvg), node;
          if (item.kind === 'text') {
            node = doc.createElementNS(NS, 'text');
            node.setAttribute('x', pts[0][0]); node.setAttribute('y', pts[0][1]);
            node.setAttribute('transform', 'rotate(' + Math.atan2(pts[1][1]-pts[0][1],pts[1][0]-pts[0][0])*180/Math.PI + ' ' + pts[0][0] + ' ' + pts[0][1] + ')');
            node.setAttribute('font-size', Math.hypot(pts[1][0]-pts[0][0],pts[1][1]-pts[0][1])*item.size);
            node.setAttribute('font-weight','700'); node.setAttribute('text-anchor','middle');
            node.setAttribute('fill',item.color); node.setAttribute('stroke','#000');
            node.setAttribute('paint-order','stroke'); node.style.setProperty('stroke-width','0.8px','important');
            node.textContent = item.text;
          } else {
            node = doc.createElementNS(NS, item.kind === 'polygon' ? 'polygon' : 'polyline');
            node.setAttribute('points', pts.map(function (p) { return p.join(','); }).join(' '));
            node.setAttribute('fill', item.kind === 'polygon' ? '#07131f' : 'none');
            node.setAttribute('fill-opacity','0.65'); node.setAttribute('stroke',item.color);
            node.style.setProperty('stroke-width','2px','important');
          }
          node.setAttribute('vector-effect','non-scaling-stroke'); group.appendChild(node);
          if (options.item && item.kind === 'polygon') node._geometryItem = options.item;
        });
        parent.appendChild(group);
      });
    }
  };
})();
