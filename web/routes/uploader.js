var express = require('express');
var router = express.Router();


// app.get('/uploader', function(req, res){
//   res.sendFile(path.join(__dirname, 'views/fileUploader.html'));
// });

router.get('/', function(req, res, next) {
  res.render('fileUploader');
});


router.post('/upload', function(req, res){
    console.log('found upload!!!!!')

  // create an incoming form object
  var form = new formidable.IncomingForm();

  // specify that we want to allow the user to upload multiple files in a single request
  form.multiples = true;

  // store all uploads in the /uploads directory
  // form.uploadDir = path.join(__dirname, '/files/updates');
  // form.uploadDir = path.join(__dirname, '/updates');
  form.uploadDir = path.join(__dirname, 'updates');
  console.log('found upload!!!!!')

  // every time a file has been uploaded successfully,
  // rename it to it's orignal name
  form.on('file', function(field, file) {
      console.log(field)
      console.log(file)
    fs.rename(file.path, path.join(form.uploadDir, file.name));
  });

  // log any errors that occur
  form.on('error', function(err) {
    console.log('An error has occured: \n' + err);
  });

  // once all the files have been uploaded, send a response to the client
  form.on('end', function() {
    res.end('success');
  });

  // parse the incoming request containing the form data
  form.parse(req);

});


module.exports = router;
