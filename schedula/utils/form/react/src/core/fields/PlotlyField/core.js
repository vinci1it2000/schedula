import React from "react";
import cloneDeep from 'lodash/cloneDeep'
import Plotly from "plotly.js-cartesian-dist-min";
import createPlotlyComponent from "react-plotly.js/factory";
import {getUiOptions} from "@rjsf/utils";
import {useResizeDetector} from 'react-resize-detector'

const Plot = createPlotlyComponent(Plotly);

export function ResponsivePlot({layout, ...props}) {
    const {width, height, ref} = useResizeDetector({
        refreshMode: 'debounce',
        refreshRate: 50
    })
    return (
        <div ref={ref} style={{display: 'flex', height: '100%'}}>
            <Plot layout={{...layout, width, height}} {...props}/>
        </div>
    )
}

export default function PlotlyField({uiSchema, formData}) {
    const {data, layout = {}} = formData, options = getUiOptions(uiSchema);
    return <ResponsivePlot
        data={cloneDeep(data)}
        layout={cloneDeep({autosize: true, ...layout})}
        useResizeHandler={true}
        config={{responsive: true}}
        style={{width: "100%", height: "100%"}}
        {...options}
    />;
}
