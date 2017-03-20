#!/usr/bin/env node

var express = require('express');
var path = require('path');
var logger = require('morgan');
var cookieParser = require('cookie-parser');
var bodyParser = require('body-parser');

var mongoose = require('mongoose');
require('./models/Devices');

var index = require('./routes/index');


mongoose.connect('mongodb://localhost/sensors');


var app = express();


// view engine setup
app.set('views', path.join(__dirname, 'views'));
app.set('view engine', 'ejs');


// Standard express setup
app.use(logger('dev'));
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({extended: false}));
app.use(cookieParser());
app.use(express.static(path.join(__dirname, 'public')));


app.use('/', index);


// catch 404 and forward to error handler
app.use(function (req, res, next) {
  var err = new Error('Not Found');
  err.status = 404;
  next(err);
});

// // development error handler
// app.use(function (err, req, res, next) {
//   console.log('error b', err.message);
//   res.status(err.status || 500);
//   res.render('index', { error: err });
// });

app.use(function(err, req, res, next) {
  // set locals, only providing error in development
  res.locals.message = err.message;
  res.locals.error = req.app.get('env') === 'development' ? err : {};

  // render the error page
  res.status(err.status || 500);
  res.render('error');
});


app.set('port', process.env.PORT || 3000);


var server = app.listen(app.get('port'), function () {
  console.log('Express server listening on port ' + server.address().port);
});
