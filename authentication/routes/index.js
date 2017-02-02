var express = require('express');
var router = express.Router();

var passwordless = require('passwordless');

function respondWithUser (req, res) {
  res.json({ user: req.user });
}

/* GET home page. */
router.get('/', respondWithUser);

/* GET restricted site. */
router.get('/restricted', passwordless.restricted(), respondWithUser);

/* GET login screen. */
router.get('/login', respondWithUser);

/* GET logout. */
router.get('/logout', passwordless.logout(), respondWithUser);

/* POST login screen. */
router.post('/sendtoken',
  passwordless.requestToken(
    // Simply accept every user
    function (user, delivery, callback) {
      callback(null, user);
    }),
    function (req, res) {
      res.json({ 'sentToken': true });
    });

module.exports = router;
