/* globals d3 */

function initUI () {
  var sidebar = d3.select('#sidebar');

  // for now have it collapsed
  sidebar.classed('collapsed', true);

  sidebar.select('#hamburger').on('click', function () {
    sidebar.classed('collapsed', !(sidebar.classed('collapsed')));
  });
}

window.onload = function () {
  initUI();
};
