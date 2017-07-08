///////////////////
//   VARIABLES   //
///////////////////


//Global Variables
//let t0 = performance.now();
let globalAnnotations = [];         // global container for annotations
let globalExtent = [];              // the extent of the entire dataset (dates as ms)
let globalMax = [];                 // the largest value in the entire dataset

let selectedExtent = [];            // Keep track of current selected daterange (as ms)
let selectedMax = [];               // the max. value in currently highlighted region

let brushStart = [];                // the start of a current brush selection
let brushMid = [];                  // the midpoint of a brush selection
let brushEnd = [];                  // the end of a current brush selection


let scaledDatasets = [];            // Container for all scaled datasets
let loadedDataset = [];             // the dataset which is most relevant to use

let home = "";                      // Home ID
let startTime;                      // Keeps track of when you click, and the length of time you press
let coords = [];                    // stores x,y coords of a mouse click / touch interaction
let timeWindow = 12*60*60*1000;     // Stores brushwidth.  default value to start


let dt = 500;                       // transition duration  (coded but not used)
let easing = d3.easeQuad;           //easing method         (coded but not used)

let scaleType = "";                 //choose what scale type we're using (Log or linear)

let colorList=["#a6cee3","#1f78b4","#b2df8a","#33a02c","#fb9a99","#e31a1c","#fdbf6f","#ff7f00","#cab2d6","#6a3d9a"];
// let baseURL = "https://viz.app.lundrigan.org";
let updateTime = 60;   // Refresh rate (in seconds)

//define canvas
let svg = d3.select("svg"),   //Define graph sizes
    margin = {top: 90, right: 45, bottom: 10, left: 5},
    margin2 = {top: 20, right: 45, bottom: 415, left: 5},
    width = +svg.attr("width") - margin.left - margin.right,
    height = +svg.attr("height") - margin.top - margin.bottom,
    height2 = +svg.attr("height") - margin2.top - margin2.bottom;

let g = svg.append("g").attr("transform","translate(" + margin.left + "," + margin.top + ")");

g.append("defs").append("clipPath")
    .attr("id", "clip")
    .append("rect")
    .attr("width", width)
    .attr("height", height);
let textBox = svg.append("text");

//Scales & Axes
let xScale = d3.scaleTime().range([0, width]),
    x2Scale = d3.scaleTime().range([0, width]).clamp(true),
    yScale = d3.scaleLinear().domain([0,40]).range([height, 0]),
    y2Scale = d3.scaleLinear().range([height2, 0]);
let xAxis = d3.axisBottom(xScale)
        .tickSize(-height)
        .tickPadding(6),
    yAxis = d3.axisLeft(yScale)
        .tickSize(-width)
        .tickPadding(8);
let xAxis2 = d3.axisBottom(x2Scale)
    .tickSize(-height2)
    .tickPadding(6);

//define transforms
let line = d3.line()
    .x(function(d) {
        return xScale(d[0]);
    })
    .y(function(d) {
        if(d[2]==0){
            //console.log("ruh-roh");
            return yScale(1);
        }else{
            return yScale(d[2]);
        }

    });
let line2 = d3.line()
    .x(function(d) {
        return x2Scale(d[0]);
    })
    .y(function(d) { return y2Scale(d[2]); });

//define main graph
let focus = svg.append("g")
    .attr("class", "focus")
    .attr("transform", "translate(" + margin.left + "," + margin.top + ")");
// text label for the y axis
focus.append("text")
    .attr("y", -7)
    .attr("x",width+30 )
    .attr("dy", "1em")
    .style("text-anchor", "start")
    .text("PM Cnt.");
//Add x-axis
let xAxisGroupFocus = focus.append("g")
    .attr("class", "axis axis--x")
    .attr("transform", "translate(0," + height + ")")
    .call(xAxis);

//add the Y Axis
let yAxisGroupFocus = focus.append("g")
    .attr("class", "axis axis--y")
    .attr("transform", "translate( " + (width) + ", 0 )" )
    .call(d3.axisRight(yScale)
        .ticks(5)
        .tickFormat(d3.format(".1s",1e3)));

//add the brush viewstrip
let context = svg.append("g")
    .attr("class", "context")
    .attr("transform", "translate(" + margin2.left + "," + margin2.top + ")");

//Add x-axis to brush plot
let xAxisGroupBrush = context.append("g")
    .attr("class", "axis axis--x")
    .attr("transform", "translate(0," + height2 + ")")
    .call(xAxis2);

// let annotationPane = svg.append("g")
//     .attr("class", "annotations")
// .attr("id","annotations");
//     // .attr("transform", "translate(" + margin.left + "," + margin.top + ")");
//
// let annotationBrushPane =svg.append("g")
//     .attr("class", "brushAnnotations")
//     .attr("transform", "translate(" + margin.left + "," + margin2.top + ")");


// modify the height of the svg to add the annotations at the bottom
d3.select('svg').attr('height', 550);

// annotationPane.attr("transform", "translate(" + margin.left + "," + (height+100)+ ")"); //change multiplying factor to move the annotation pane closer to SVG plot
// annotationPane.append('rect')
//     .attr('width', 720)
//     .attr('height', 30)
//     .attr('y', 14)
//     .style('fill', 'none')
//     .style('stroke', '#d0d0d0')
//     .style('stroke-width', 1);


//define brushing behavior
let brush = d3.brushX()
    .extent([[0, 0], [width, height2]])
    .on("brush", brushed);                //NOTE:  change brush activation to affect scrolling
                                        // "brush" --> update on scroll.
                                        // "end" --> update after scroll
let slider = context.append("g")
    .attr("class", "brush")
    .attr("id","slider")
    .call(brush)
    //.call(brush.move, x2Scale.range())   //Determines the initial view
    .selectAll(".overlay")
    .each(function(d) { d.type = "selection"; })
    .on("mousedown touchstart click ", brushcentered);       // Recenter before brushing. (touchstart click)
slider.selectAll(".handle").remove();                        // Remove ability for user to re-size brush


// Prep the tooltip bits, initial display is hidden
let tooltip = svg.append("g")
    .attr("class", "tooltip")
    .style("display", "none"); // start tooltip as hidden

tooltip.append("text")
    .attr("x", 15)
    .attr("dy", "1.2em");

//Add event listener to time series buttons
let selectorButtonsParent=document.getElementById("btnDiv");
selectorButtonsParent.addEventListener("click",drawBrush,false);

///////////////////////
//    Modal Vars     //
///////////////////////

let modal = document.getElementById('myModal');// Get the modal
let loadingScreen = document.getElementById('loadingModal');
let span = document.getElementsByClassName("close")[0];             // Get the <span> element that closes the modal
span.onclick = closeModalWindow;                                    // When the user clicks on <span> (x), close the modal
// let modalSubmit = document.getElementsByClassName("modalSubmit")[0];
// modalSubmit.onclick = handleModalSubmission;                        //when the user clicks on the submit button
let textArea = document.getElementsByClassName("textArea")[0];

//add a listener to the SVG to tell when we are pressing
let touchpane = svg.append("g").attr("id","touchPane")
    .attr("transform","translate(" + margin.left + "," + margin.top + ")");

let trect = touchpane.append("rect")
    .attr("id","touchRect")
    .attr("width",width)
    .attr("height",height);

touchpane
    .on('touchstart', function() {
        i=1;
        clicked = true;
        coords = d3.mouse(this);
        click(); })   // Registered on touch devices?
    .on('mousedown', function() {
        coords = d3.mouse(this);
        console.log("You Clicked (x,y): (",coords[0],",",coords[1],")");
        console.log("Date:",xScale.invert(coords[0]));

        i=1; clicked = true; click(); })   // Registered from mouse.
    .on('mouseup',function() { clicked = false; })
    .on('mouseout',function() { clicked = false; });



//Defining variables 12 - 16 ms
///////////////////
//  STATEMENTS   //
///////////////////

window.onload=getDatasets(); //second parameter determines time averaging.
setInterval(getDatasets, updateTime*1000);

// When the user clicks anywhere outside of the modal, close it
window.onclick = function(event) {
    if (event.target == modal) {
        modal.style.display = "none";
    }
};

///////////////////
//  FUNCTIONS    //
///////////////////

function getDatasets(){

    displayLoadingGIF();

    checkDeploymentType().then(info => {
        console.log(info);

        if (info.type === "admin") {
            // show controls
            document.getElementById('dataSource').style.display = 'flex';

            //read home value from HTML page
            let homeSelect = document.getElementById('deploymentID');
            home = homeSelect.options[homeSelect.selectedIndex].value;
            return pullFromInflux(home);
        } else {
            return pullFromInflux();
        }//end if-else

    }).then(data => {

        //Update globals with this new data:
        scaledDatasets = {
          'day': [{'id': 'tony', 'name': 'tony outside', 'active': true, 'location': 'outside', 'values': data.results[0].series[0].values, 'tags': {'entity_id': "tony"}}],
          'full': [{'id': 'tony', 'name': 'tony outside', 'active': true, 'location': 'outside', 'values': data.results[0].series[0].values, 'tags': {'entity_id': "tony"}}],
          'six': [{'id': 'tony', 'name': 'tony outside', 'active': true, 'location': 'outside', 'values': data.results[0].series[0].values, 'tags': {'entity_id': "tony"}}],
          'three': [{'id': 'tony', 'name': 'tony outside', 'active': true, 'location': 'outside', 'values': data.results[0].series[0].values, 'tags': {'entity_id': "tony"}}],
          'twelve': [{'id': 'tony', 'name': 'tony outside', 'active': true, 'location': 'outside', 'values': data.results[0].series[0].values, 'tags': {'entity_id': "tony"}}],
          'twoDay': [{'id': 'tony', 'name': 'tony outside', 'active': true, 'location': 'outside', 'values': data.results[0].series[0].values, 'tags': {'entity_id': "tony"}}],
          'week': [{'id': 'tony', 'name': 'tony outside', 'active': true, 'location': 'outside', 'values': data.results[0].series[0].values, 'tags': {'entity_id': "tony"}}]
        }
        globalMax = 50;
        globalExtent = [data.results[0].series[0].values[0][0], data.results[0].series[0].values[data.results[0].series[0].values.length-1][0]];
        // globalAnnotations  = formatAnnotations(data.events);
        loadedDataset = selectScaledDatasets(0);  // 0 is default view
        convertTimestamps(scaledDatasets);

        //Utility function, let us know what things are
        printGlobals();

        //reset the button appearances
        //d3.selectAll(".sbtn").attr("class","sbtn");
        x2Scale.domain(globalExtent);

        //move the d3 brush position BACK to where the user was looking at last.
        moveBrushToLastPosition();


        renderBrushView(globalExtent, globalMax, loadedDataset);  // ~15 ms to run

        hideLoadingGIF();

        update(loadedDataset,globalAnnotations);

    }).catch(function(err){

        hideLoadingGIF();
        alert("error, request failed!");
        console.log("Error: ",err)

    }); //fulfillment / catch

}//end getDatasets()
function moveBrushToLastPosition() {

    if (selectedExtent.length==0) {
        //if here, then selectedExtent is empty.  need to manually define.
        selectedExtent = globalExtent;
        console.log("selectedExent is empty");

        console.log("the selectedextent: " + selectedExtent)
        //highlight the entire view
        context.select(".brush").call(brush.move, [x2Scale(selectedExtent[0]), x2Scale(selectedExtent[1])]);
    } else {
        // if (d3.select('button.clicked').empty()) {
        //   selectedExtent = globalExtent;
        //
        // }

        console.log("the selectedextent: " + selectedExtent)

        console.log("SElectedExtent has a value.");
        context.select(".brush").call(brush.move, [x2Scale(selectedExtent[0]), x2Scale(selectedExtent[1])])
    }//end if-esle

}//end moveBrushtoLastPosition
function convertTimestamps(data){

    // Convert all timestamps to Date objects
    // data.values.forEach(function(element) {
    //   element[0] = new Date(element[0])
    // })
    Object.entries(data).forEach(([key, value], index) => {
        scaledDatasets[key].forEach(function(monitor){
            monitor.values.forEach(function(measure){
                measure[0] = new Date(measure[0])       //Convert string timestamps to Date object
            });
        });
    });


}//end convertTimestamps()
function printGlobals(){

    console.log("++++++++++++++++++++++++");
    console.log("Global Max: ",globalMax);
    console.log("Global Extent: ",globalExtent);
    console.log("Global Annotations: ",globalAnnotations);
    console.log("Selected Extent: ", selectedExtent);
    console.log("++++++++++++++++++++++++");
}
function renderBrushView(globalExtent, globalMax, loadedDataset){

    //set Brush Ranges...
    x2Scale.domain(globalExtent);
    y2Scale.domain([0,globalMax*1.1]);

    //set brush x-axis
    xAxisGroupBrush.call(xAxis2);

    brushMid = width/2;                //hard code to be the center of our plot range
    brushStart = x2Scale(globalExtent[0]);
    brushEnd = x2Scale(globalExtent[1]);


    let brushPath = context.selectAll(".line")
        .data(loadedDataset,function(monitor){
            return monitor.tags.entity_id;
        });

    let brushPathEnter = brushPath.enter().append('path');

    brushPath.exit().remove();

    brushPath = brushPath.merge(brushPathEnter);

    brushPath
        .attr("class", "line")
        .attr("id",function(monitor){return monitor.tags.entity_id;})
        .attr("d",  function(monitor) {
            return line2(monitor.values);})
        .style("stroke",assignColor);


    // //update annotations
    // if(typeof globalAnnotations !='undefined'){  //.....If you actually have annotations to add.....
    //     //Draw evets on the brush panel
    //     drawBrushAnnotations(globalAnnotations)
    //
    // } else{                                //....if you don't have any new annotations, remove them.....
    //     annotationBrushPane.selectAll("rect").remove();
    //     console.log(">>NO ANNOTATIONS");
    // }//end if-else

}//end renderBrushView()
function selectScaledDatasets(selection){
    switch(selection){
        case 3:
            //load 3 hour view
            loadedDataset = scaledDatasets["three"];
            break;
        case 6:
            //load 6-hour view
            loadedDataset = scaledDatasets["six"];
            break;
        case 12:
            //load 12-hour view
            loadedDataset = scaledDatasets["twelve"];
            break;
        case 24:
            //load 24-hour view
            loadedDataset = scaledDatasets["day"];
            break;
        case 48:
            //load 48-hour view
            loadedDataset = scaledDatasets["twoDay"];
            break;
        case 168:
            //load 168 hour view
            loadedDataset = scaledDatasets["week"];
            break;
        default:
            //load the entire dataset view (coarsest).
            loadedDataset = scaledDatasets["full"];
            break;
    }//end switch selection

    return loadedDataset;

}//end function selectScaledDatasets()
function performanceOutput(t0,t1,descriptionString){

    let time = Math.round(t1-t0);
    console.log("*****************************************");
    console.log("*                                                    *");
    console.log ("*  " + descriptionString + ": " +  time + " ms * ");
    console.log("*                                                    *");
    console.log("*****************************************");
}
function formatAnnotations(annotations){
    annotations.forEach(function(annotation){
        annotation[0] = new Date(annotation[0]);
    });
    return annotations;
}//end formatAnnotations()
function checkDeploymentType() {
    // let auth = getJsonFromUrl().auth;
    // var url = baseURL + "/account?auth=" + auth;

    var url = "http://air.eng.utah.edu:8086/query?db=airU&epoch=ms&q=SELECT%20ID,%22PM2.5%22%20FROM%20airQuality%20WHERE%20ID=%27A81B6A780279%27"

    return new Promise((resolve, reject) => {

        let method = "GET";  //For reading data
        let async = true;
        let request = new XMLHttpRequest();

        request.open(method, url, async); // true => request is async

        // If the request returns succesfully, then resolve the promise
        request.onreadystatechange = function() {
            if (request.readyState == 4 && request.status == 200) {
                let response =JSON.parse(request.responseText);
                resolve(response);
            } //end if request

            // If request has an error, then reject the promise
            request.onerror = function(e, i) {
                console.log("Something went wrong....");
                reject(e);
            };
        };

        request.send();

    });//end return new Promise()
}//end checkDeploymentType()
function pullFromInflux(home) {

    console.log("home: " + home);

    // let auth = getJsonFromUrl().auth;
    // var url = baseURL + "/data?auth=" + auth;
    var url = "http://air.eng.utah.edu:8086/query?db=airU&epoch=ms&q=SELECT%20ID,%22PM2.5%22%20FROM%20airQuality%20WHERE%20ID=%27A81B6A780279%27"

    if(home !== undefined) {
        url += "&home_id=" + home;
    }

    return new Promise((resolve, reject) => {

        let method = "GET";  //For reading data
        let async = true;
        let request = new XMLHttpRequest();

        request.open(method, url, async); // true => request is async

        // If the request returns succesfully, then resolve the promise
        request.onreadystatechange = function() {
            if (request.readyState == 4 && request.status == 200) {
                let response =JSON.parse(request.responseText);
                resolve(response);
            } //end if request

            // If request has an error, then reject the promise
            request.onerror = function(e, i) {

                console.log("Something went wrong....");
                reject(e);
            };
        };

        request.send();

    });//end return new Promise()
}//end function pullFromInflux()
function displayLoadingGIF(){
    //pick the gif to use
    d3.select("#loadingGif").attr("src","gif/loading6.gif");
    loadingScreen.style.display = "block";
}
function hideLoadingGIF(){
    loadingScreen.style.display = "none";
}
function getDateExtent(dataset){

    let extents  = dataset.map(function(monitor){
        return d3.extent(monitor.values, function(entry){ return entry[0];});
    });

    let extent = [d3.min(extents, function(d){ return d[0]; }),
        d3.max(extents, function(d){ return d[1]; }) ];

    return extent;

}//end function getDateExtent()
function maxValueInExtent(dataset){

    let tmp = 0,
        max = 0;

    dataset.forEach(function(monitor){

        if(monitor.active==true){

            tmp = Math.max.apply(Math, monitor.values.map(function(o){return o[2];}));

            if(tmp>max){

                max=tmp;
            }//end if tmp
        }//end if monitor.active
    });//end forEach()

    // max = Math.max.apply(Math, dataset.values.map(function(o){return o[2];}))

    return max;

}//end function maxValueInExtent()
function setYDomain(scaleType){
    let dom = [];
    switch(scaleType){
        case"linear":
            dom = [0,selectedMax*1.1];
            break;
        case"log":
            dom = [Math.exp(1),selectedMax*1.1];
            break;
        default:
            dom = [0,selectedMax*1.1];
            break
    }//end switch(scaleType)

    return dom;
}//end function setYDomain
function update(dataset,annotations){

    //determine extent of data stream'
    //selectedExtent = getDateExtent(dataset);    // 0 - 3 ms to run

    //determine maxes of datastream
    selectedMax = maxValueInExtent(dataset);   // 0 ms to run

    //Assign focus domains
    xScale.domain(selectedExtent);
    yScale.domain(setYDomain(scaleType)).clamp(true);


    //Apply new domain to x-axis
    xAxisGroupFocus.call(xAxis);

    //update focus y-axis
    yAxisGroupFocus
        //.transition()           // apply a transition
        //.ease(easing)           // control the speed of the transition
        //.duration(dt)
        .call(d3.axisRight(yScale)
            .ticks(5)
            .tickFormat(d3.format(".1s",1e3)));

    //Update the plotted line of large graph
    updateFocusLines(dataset);      // 4 - 10 ms to run

    //Add items to the legend
    updateLegend(dataset);          // 0 ms to run

    //update  s
    // updateAnnotations(annotations);     // 0 - 1 ms to run

    //TODO: Resize yScale on button click?
}//end function update()
function updateAnnotations(annotations){
    if(typeof annotations !='undefined'){
        //.....If you actually have annotations to add.....
        drawFocusPaneAnnotations(annotations);

    } else{
        //....if you don't have any new annotations, remove them.....
        annotationPane.selectAll("rect").remove();
    }//end if-else
}//end function updateAnnotations()
function updateFocusLines(data){

    let pmLines = focus.selectAll(".line")
        .data(data, function(monitor){
            return monitor.tags.entity_id;
        });

    pmLines.exit().remove();

    let myPathEnter = pmLines.enter()
        .append("path")
        .attr("class", "line")
        .attr("id",function(monitor){return monitor.tags.entity_id;});

    pmLines = pmLines.merge(myPathEnter);

    pmLines
        //.transition()
        //.ease(easing)
        //.duration(dt)
        .attr("d",  function(monitor) {
            return line(monitor.values);
        })
        .attr("class", function(monitor){
            return "line "+monitor.tags.entity_id;
        })
        .style("stroke",assignColor);

}//end function updateFocusLines
function assignColor(data,i){

    var col = [];

    if(data.location==="outside"){
        col = "orange";
    } else {
        col = colorList[i];
    }//end if-else

    return col;
}//end function setMonitorColors
function updateLegend(data){

    let legend = d3.select(".legend").selectAll("p")
        .data(data, function(monitor){
            var monitorID = monitor.tags.entity_id.split("_")[0];
            return monitorID;
        });

    legend.exit().remove();

    let legendEnter = legend.enter()
        .append("p")
        .attr("class","legendItem");
    //console.log("Entering selection: ",legendEnter);
    legend = legend.merge(legendEnter);
    legend.style("border-color",assignColor)
        .text(function(monitor){
            if (monitor.name == "") {
                return monitor.id + " (" + monitor.location + ")";
            } else {
                return monitor.name;
            }
        })
        .style("color", assignColor)
        .attr("id",function(monitor){return monitor.tags.entity_id;})
        .on("click",function(monitor){

            //Variables
            let tag = monitor.tags.entity_id;
            let monID = tag.split("_")[0];
            let active   = monitor.active ? false : true;
            let newOpacity = active ? 1 : 0;
            monitor.active = active;

            //Statements
            // console.log("Active is",active);
            // console.log(monID," is ",monitor.active);
            // console.log(monitorPlacementLUT(home,monID ), " is now ", active);

            // Hide or show the elements
            focus.select("#"+tag).style("opacity", newOpacity);
            context.select("#"+tag).style("opacity", newOpacity);
            d3.select(".legend").select("#"+tag).classed("deactivate",!monitor.active);


            //============ Dynamically Update Y-Axis ==============//
            //
            //     TODO:  figure out how to re-scale the y-axis
            //
            //============ ######################### ==============//

            //Not working how I expect -- recenters the
            update(data,globalAnnotations);
        });
}//end updateLegend
function drawBrushAnnotations(annotations){

    let brushEvents = annotationBrushPane.selectAll("rect")
        .data(annotations,function(event){
            return event[0];
        });

    brushEvents.exit().remove();

    let brushEventsEnter = brushEvents.enter().append("rect");

    brushEvents = brushEvents.merge(brushEventsEnter);
    brushEvents
        .attr("class","glyph")
        .attr("width",2)
        .attr("height",2)
        .attr("y",5)
        .attr("x",function(event){return x2Scale(event[0]);});
}// end drawBrushAnnotationS()
function drawFocusPaneAnnotations(data){

    let events = annotationPane.selectAll("text.glyph")
        .data(data,function(event){
            return event[0];
        });

    events.exit().remove();

    let eventsEnter = events.enter().append("text");

    events = events.merge(eventsEnter);
    events

        //Different Icon Parameters
    //  - Asterix: \ufo69 size 1.1em, y=25 x= scale-10
    // - Triangle: \uf0de size 2em, y= 33   x = scale - 10
        .attr("class","glyph")
        .attr("id","glyph")
        .attr('font-size','5em')
        .attr("y",60)
        .attr("x",function(event){return xScale(event[0])-19;})
        .text('\uf0de')
        .on("click",function(){

            tooltip.style("display", null);
        })
        .on("mouseenter", function(annotation) {

            //Note!
            // annotation[0]: timestamp
            // annotation[1]: message

            d3.select(this).classed("active",true);

            //tooltip.attr("transform", "translate(" + xPosition + "," + yPosition + ")");

            tooltip.style("display", null);

            //Determine what happens with our tool tip text
                textBox.text(truncate(annotation[1]))
                .attr("class","annoText")
                .attr("x",((width/2)+margin.left))              // start writing text at center of SVG
                .attr("y",height+margin2.top+margin.top+55);       // positon text below the glyph box;

            //Determine what happens with our tool tip text
            // tooltip.select("text")
            //     .text(truncate(annotation[1]))
            //     .attr("class","annoText")
            //     .attr("text-anchor","middle")                   // grab center of text string
            //     .attr("x",((width/2)+margin.left))              // start writing text at center of SVG
            //     .attr("y",height+margin2.top+margin.top);       // positon text right above the glyph box;

            drawOverLine(xScale(annotation[0]));
          })
          .on("mouseleave", function(annotation) {

              //Note!
              // annotation[0]: timestamp
              // annotation[1]: message

              //erase textbox
              textBox.text("");

              //erase guide-line
              d3.select(".overLine").remove();

              //un-highlight glyph
              d3.select(this).classed("active",false);

              //remove tooltip
              tooltip.style("display", 'none');

          });

} // end drawFocusPaneAnnotations
function drawOverLine(pos) {
    svg.append("line")
        .attr("class","overLine")
        .attr("transform","translate(0," + margin.top + ")")
        .attr("y1", height)
        .attr("y2", 0)
        .attr("x1", pos)
        .attr("x2", pos);
}//end function drawOverline
function setLinearScale(){
    yScale = d3.scaleLinear().range([height, 0]);
    update(loadedDataset,globalAnnotations);
}//end function setLinearScale();
function setLogScale(){

    yScale = d3.scaleLog().range([height,0]);
    update(loadedDataset,globalAnnotations);

}//end function setLogScale()
function setScale(){

    let sel = document.getElementById('scaling');
    scaleType = sel.options[sel.selectedIndex].value;
    console.log("Selection Option: ",scaleType);

    switch(scaleType){
        case "linear":
            setLinearScale();
            break;
        case "log":
            setLogScale();
            break;
        default:
            setLinearScale();
            break;
    }//end switch(scaleType)
}//end function setScale
function findClosestIndex(data,date){

    //Good old-fashioned binary search
    var lo = -1, hi = data.length;

    while (hi - lo > 1) {
        let mid = Math.round((lo + hi)/2);

        if (data[mid][0] <= date) {
            lo = mid;
        } else {
            hi = mid;
        }//end if-else

    }//end while()

    //This check will cause an error if the left brush edge does not fall on the left most
    // dataset boundary. In this case, lo will never update to zero and will stay at -1
    // this attempts to read data[-1][0] which obviously throws an error, but doesn't break the
    // code operation.

    // if (data[lo][0] == date){
    //     hi = lo;
    // } //end if

    // if lo = -1 at this location, it means we are at the left-most boundary.
    // Manually set lo = 0 .

    if(lo == -1){
       lo = 0;
    }

    return [lo,hi];
}//end function findClosestStartIndex()
function dataInSelection(data,selectedExtent){

    let start = selectedExtent[0];
    let stop = selectedExtent[1];
    let dataInScope = [];

    data.forEach(function(monitor,i){

        let startIndex = findClosestIndex(monitor.values,start);
        let low_val = startIndex[0]; //choose the low index

        let stopIndex = findClosestIndex(monitor.values,stop);
        let high_val = stopIndex[1] + 1; //NOTE:   The findClosestIndex() algo seems to be 1 shy when reporting the upper
                                         // upper bound.  fencepost error?

        //TODO:  Figure out why the search algorithm has fencepost error.  for now, we manually correct it.

        dataInScope[i] = JSON.parse(JSON.stringify(monitor));

        dataInScope[i].values = monitor.values.slice(low_val, high_val)

    });

    return dataInScope;

}//end function dataInSelection()
function brushed() {


    //remove handles from slider
    d3.selectAll(".brush").select(".handle").remove();

    //remove all overlaid lines
    d3.select(".overLine").remove();

    //Get and set date extent
    let s = d3.event.selection || x2Scale.range();

    brushMid = getBrushCenter(s);

    //console.log("Extent: ",s);
    //console.log("Data: ",loadedDataset);
    selectedExtent = [x2Scale.invert(s[0]).getTime(),x2Scale.invert(s[1]).getTime()];


    let dataInScope = dataInSelection(loadedDataset, selectedExtent);

    selectedMax = maxValueInExtent(dataInScope);

    //-------  THis is where the call to update() should be --------------------//

    update(dataInScope,globalAnnotations);

}//end function brushed()
function brushcentered() {

    let cx = d3.mouse(this)[0];
    let dx = timeWindow*60*60*1000;

    let x0 = x2Scale( +x2Scale.invert(cx) - dx / 2);
    let x1 = x2Scale( +x2Scale.invert(cx) + dx / 2);

    //determine brushStart
    if(x0<0){
        brushStart = 0;

    } else{
        brushStart = x0;
    }//end if-else

    //Determine  brushEnd
    if(x1<width){
        brushEnd = x1;
    }else{
        brushEnd = width;
    }//end if-else

    brushMid = getBrushCenter([brushStart,brushEnd]);           //define current center of brush
    selectedExtent = [x2Scale.invert(x0),x2Scale.invert(x1)];   //define selected extent

    d3.select(this.parentNode).call(brush.move, [brushStart,brushEnd]); //move brush

}//end function brushCentered()
function getBrushCenter(s){
    return(s[0] + s[1])/2;
}//end function getBrushCenter();
function getButtonSelection(e){

    //Check if the clicked target is the parent div or not
    if (e.target !== e.currentTarget) {
        timeWindow = e.target.value;                                        //get button value
        d3.selectAll(".sbtn").attr("class","sbtn");                         //turn off all button styling
        this.d3.select("#b"+timeWindow+"h").attr("class","sbtn clicked");   //style *this* button as active
    }//end if

    e.stopPropagation();

    return Number(timeWindow)

}//end function getButtonSelection()
function drawBrush(e) {

    //remove resizing handles from brush
    d3.selectAll(".brush").select(".handle").remove();


    timeWindow = getButtonSelection(e);
    loadedDataset = selectScaledDatasets(timeWindow);

    let midpoint = x2Scale.invert(brushMid);

    let start = new Date (+midpoint - timeWindow*60*60*1000/2);
    let end = new Date (+midpoint + timeWindow*60*60*1000/2);

    selectedExtent = [start.getTime(),end.getTime()];
    console.log("The selected extend: " + selectedExtent);

    brushStart = x2Scale(start);
    brushEnd = x2Scale(end);

    context.select(".brush").call(brush.move, [brushStart, brushEnd]);
}//end function drawBrush(e)
function largestTriangleThreeBuckets(data, threshold) {

    //Code taken from Sveinn Steinarsson's Downsample Algorithm
    //Github: https://github.com/sveinn-steinarsson/flot-downsample/blob/master/jquery.flot.downsample.js
    //Thesis: http://skemman.is/stream/get/1946/15343/37285/3/SS_MSthesis.pdf
    //With some mild modifications

    let floor = Math.floor,
        abs = Math.abs;

    let data_length = data.length;

    if (threshold >= data_length || threshold === 0) {
        return data; // Nothing to do
    }

    let sampled = [],
        sampled_index = 0;

    // Bucket size. Leave room for start and end data points
    let every = (data_length - 2) / (threshold - 2);

    let a = 0,  // Initially a is the first point in the triangle
        max_area_point,
        max_area,
        area,
        next_a;

    sampled[ sampled_index++ ] = data[ a ]; // Always add the first point

    for (var i = 0; i < threshold - 2; i++) {

        // Calculate point average for next bucket (containing c)
        let avg_x = 0,
            avg_y = 0,
            avg_range_start  = floor( ( i + 1 ) * every ) + 1,
            avg_range_end    = floor( ( i + 2 ) * every ) + 1;
        avg_range_end = avg_range_end < data_length ? avg_range_end : data_length;

        let avg_range_length = avg_range_end - avg_range_start;

        for ( ; avg_range_start<avg_range_end; avg_range_start++ ) {

            //IMPORTANT
            //  This code needs to be changed depending on the object packagingg
            avg_x += data[ avg_range_start ][ 0 ] * 1; // * 1 enforces Number (value may be Date)
            avg_y += data[ avg_range_start ][ 1 ] * 1; // This should be the measurement value

        } //end for
        avg_x /= avg_range_length;
        avg_y /= avg_range_length;

        // Get the range for this bucket
        let range_offs = floor( (i + 0) * every ) + 1,
            range_to   = floor( (i + 1) * every ) + 1;

        // Point a

        //NOTE::   Data[] access needs to be formatted to match the dataobject.
        let point_a_x = data[ a ][ 0 ] * 1, // enforce Number (value may be Date)
            point_a_y = data[ a ][ 1 ] * 1; // measurement


        max_area = area = -1;

        for ( ; range_offs < range_to; range_offs++ ) {


            // Calculate triangle area over three buckets

            //NOTE::  Data[] access needs to be formatted to match the dataobject.
            area = abs( ( point_a_x - avg_x ) * ( data[ range_offs ][ 1 ] - point_a_y ) -
                    ( point_a_x - data[ range_offs ][ 0 ] ) * ( avg_y - point_a_y )
                ) * 0.5;


            if ( area > max_area ) {
                max_area = area;
                max_area_point = data[ range_offs ];
                next_a = range_offs; // Next a is this b
            }//end if
        }//end for

        sampled[ sampled_index++ ] = max_area_point; // Pick this point from the bucket
        a = next_a; // This a is the next a (chosen b)
    }//end for i

    sampled[ sampled_index++ ] = data[ data_length - 1 ]; // Always add last

    return sampled;
}//end function largestTriangleThreeBuckets

///////////////////////
//                   //
//  MODAL FUNCTIONS  //
//                   //
///////////////////////

function handleModalSubmission() {

    //Get Event parameters
    let inputText = textArea.value.trim();      //trim() removes any leading or trailing whitespace
    let time = d3.select("#clickedTime").text();
    let newTime = +new Date(time);
    let monitor_id = "monitor999";

    if (inputText === "") {
        //if the user enters and empty string
        alert("Text box is empty, please enter an annotation to record.");
    } else if (!inputText.replace(/\s/g, '').length) {
        //if the input text is simply a string of spaces
        alert("nice try ;-)  We still need an annotation with words!");

    } else {
        //the input string is text
        sendToInflux(inputText, newTime / 1000, monitor_id, home);

        // Create a new annotation-like object and add it to global annotations.
        let newAnnotation = [
            new Date(newTime),
            inputText];
        globalAnnotations.push(newAnnotation);

        // Reset modal window
        textArea.value = "";                          // reset text area input
        modal.style.display = "none";                 // hide the display

        // Call update
        updateAnnotations(globalAnnotations);     // 0 - 1 ms to run
        //update(loadedDataset, globalAnnotations);

    }//end if/else if/else


}//end function handleModalSubmission()
function truncate(string){
    let preview = 80;   //number of characters to write inside a tooltip


    if (string==null){
        return string;
    }else if (string.length > preview){
        return string.substring(0,preview)+'...';
    }else{
        return string;
    }

}//end function truncate()
function makeHumanReadableTime(time){
    let day = time.getDay();
    let daynum = time.getDate();
    let month = time.getMonth();
    let year = time.getFullYear();
    let dayName = disambiguateDay(day);
    let monthName = disambuguateMonth(month);
    let hours = time.getHours();
    let minutes = time.getMinutes();
    let seconds = time.getSeconds();
    let ampm = hours >= 12 ? 'PM' : 'AM';

    hours = hours % 12;
    hours = hours ? hours : 12; // the hour '0' should be '12'

    // add a zero in front of numbers<10
    minutes = checkTime(minutes);
    seconds = checkTime(seconds);

    return dayName + " " + monthName + " " + daynum +  ", " + year + " " + hours + ":" + minutes + ":" + seconds + " "+ampm;
}
function openModalWindow(){
    modal.style.display = "block";
    let time = xScale.invert(coords[0]);
    let time_string=  makeHumanReadableTime(time);
    d3.select("#clickedTime").text(time_string);
}
function closeModalWindow(){
    modal.style.display = "none";
}
function click() {
    //Kludge to detect a long press from D3
    if (clicked) {

        startTime = new Date();
        console.log("increment is: " + i);

        if (i <= 1) {
            setTimeout(function() {
                click(++i)
            }, 1750);
        }
        else if (i==2) {
            openModalWindow(coords);    //Open modal window after four iterations
        }
    }
}
function sendToInflux(event,time,monitor,home){

    console.log("The call is coming from inside the influx function!");
    console.log("Detected Event: ", event);
    console.log("Time: ", time);
    console.log("Monitor: ", monitor);
    console.log("Deployment: ", home);



    // Following code graciously appropriated from
    // http://stackoverflow.com/questions/14873443/sending-an-http-post-using-javascript-triggered-event
    // let url = "https://prisms.app.lundrigan.org/write?db=home_assistant&u=prisms&p=air_quality?&precision=s";
    let auth = getJsonFromUrl().auth;
    var url = baseURL + "/event?auth=" + auth;

    if(home !== undefined) {
        url += "&home_id=" + home;
    }


    let method = "POST";
    let postData = JSON.stringify({
        text: event,
        time: time,
        source: "tablet"
    });

    console.log("Here is your PostData: ", postData);
    // You REALLY want async = true.
    // Otherwise, it'll block ALL execution waiting for server response.
    let async = true;

    let request = new XMLHttpRequest();

    // Before we send anything, we first have to say what we will do when the
    // server responds. This seems backwards (say how we'll respond before we send
    // the request? huh?), but that's how Javascript works.
    // This function attached to the XMLHttpRequest "onload" property specifies how
    // the HTTP response will be handled.
    request.onload = function () {

        // Because of javascript's fabulous closure concept, the XMLHttpRequest "request"
        // object declared above is available in this function even though this function
        // executes long after the request is sent and long after this function is
        // instantiated. This fact is CRUCIAL to the workings of XHR in ordinary
        // applications.

        // You can get all kinds of information about the HTTP response.
        let status = request.status; // HTTP response status, e.g., 200 for "200 OK"
        let data = request.responseText; // Returned data, e.g., an HTML document.

        console.log("Server Status: ",status);
        console.log("Server Data: ",data);
    };

    request.open(method, url, async);

    request.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
    // Or... request.setRequestHeader("Content-Type", "text/plain;charset=UTF-8");
    // Or... whatever

    // Actually sends the request to the server.
    request.send(postData);
}
function getJsonFromUrl(hashBased) {

    var query;
    if(hashBased) {
        var pos = location.href.indexOf("?");
        if(pos==-1) return [];
        query = location.href.substr(pos+1);
    } else {
        query = location.search.substr(1);
    }
    var result = {};
    query.split("&").forEach(function(part) {
        if(!part) return;
        part = part.split("+").join(" "); // replace every + with space, regexp-free version
        var eq = part.indexOf("=");
        var key = eq>-1 ? part.substr(0,eq) : part;
        var val = eq>-1 ? decodeURIComponent(part.substr(eq+1)) : "";
        var from = key.indexOf("[");
        if(from==-1) result[decodeURIComponent(key)] = val;
        else {
            var to = key.indexOf("]",from);
            var index = decodeURIComponent(key.substring(from+1,to));
            key = decodeURIComponent(key.substring(0,from));
            if(!result[key]) result[key] = [];
            if(!index) result[key].push(val);
            else result[key][index] = val;
        }
    });
    return result;
}//end function getJsonFromUrl
