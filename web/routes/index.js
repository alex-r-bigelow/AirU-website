var express = require('express');
var router = express.Router();

var passwordless = require('passwordless');

function renderIndex (req, res) {
  res.render('index', { user: req.user });
}

/* GET home page. */
router.get('/', renderIndex);

/* GET restricted site. */
router.get('/restricted', passwordless.restricted(), renderIndex);

/* GET login screen. */
router.get('/login', renderIndex);

/* GET logout. */
router.get('/logout', passwordless.logout(), renderIndex);

/* POST login screen. */
router.post('/sendtoken',
  passwordless.requestToken(
    // Simply accept every user
    function (user, delivery, callback) {
      callback(null, user);
    }),
    function (req, res) {
      res.render('index', { 'sentToken': true });
    });

module.exports = router;
