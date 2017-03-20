var mongoose = require('mongoose');
var Device = mongoose.model('Device');

var express = require('express');
var router = express.Router();


/* GET home page. */
router.get('/', function(req, res, next) {
  console.log('where am I')
    // var serverState = {};
    // serverState.user = req.user;
    // serverState.sentToken = !!(res.locals.sentToken);

  res.render('index', { title: 'Express' });
});


router.get('/devices', function (req, res, next) {
  Device.find(function (err, devices) {
    if (err) { return next(err); }

    // res.json(devices);
    res.json({ message: 'hooray! welcome to our api!' });
  });
});


router.post('/devices', function(req, res, next) {
  var device = new Device(req.body);

  device.save(function (err, device) {
    if(err) { return next(err); }

    res.json(device);
  });
});


module.exports = router;
