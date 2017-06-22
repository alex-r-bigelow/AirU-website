var express = require('express');
var router = express.Router();
var mongoose = require('mongoose');
var Sensor = require('../models/Sensors.js');

var log = require('../log.js')

/* GET ALL SENSOR */
router.get('/', function(req, res, next) {
  Sensor.find(function (err, sensors) {
    log.warn('testing');
    if (err) return next(err);
    res.json(sensors);
  });
});

/* GET SINGLE SENSOR BY ID */
router.get('/:id', function(req, res, next) {
  Sensor.findById(req.params.id, function (err, post) {
    if (err) return next(err);
    res.json(post);
  });
});

/* SAVE SENSOR */
router.post('/', function(req, res, next) {
  Sensor.create(req.body, function (err, post) {
    if (err) return next(err);
    res.json(post);
  });
});

/* UPDATE SENSOR */
router.put('/:id', function(req, res, next) {
  Sensor.findByIdAndUpdate(req.params.id, req.body, function (err, post) {
    if (err) return next(err);
    res.json(post);
  });
});

/* DELETE SENSOR */
router.delete('/:id', function(req, res, next) {
  Sensor.findByIdAndRemove(req.params.id, req.body, function (err, post) {
    if (err) return next(err);
    res.json(post);
  });
});

module.exports = router;
