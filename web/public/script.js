/* globals d3 */

function initUI () {
  var sidebar = d3.select('#sidebar');
  sidebar.select('#hamburger').on('click', function () {
    sidebar.classed('collapsed', !(sidebar.classed('collapsed')));
  });
}

window.onload = function () {
  initUI();
};
