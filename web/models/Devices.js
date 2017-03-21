var mongoose = require('mongoose');

var DeviceSchema = new mongoose.Schema({
  sensor_model: {type: String, required: true},
  sensor_version: {type: String, required: true},
  macaddress: {type: String, required: true},
  longitude: {type: Number, required: true},
  latitude: {type: Number, required: true},
  location: {type: [Number], required: true}, // [Long, Lat]
  created_at: {type: Date, default: Date.now}
  // loc: {
  //   type: [Number],  // [<longitude>, <latitude>]
  //   index: '2d'      // create the geospatial index
  // }
});


// Sets the created_at parameter equal to the current time
DeviceSchema.pre('save', function(next){
    now = new Date();
    if(!this.created_at) {
        this.created_at = now
    }
    next();
});


// Indexes this schema in 2dsphere format (critical for running proximity searches)
DeviceSchema.index({location: '2dsphere'});


mongoose.model('Device', DeviceSchema);
