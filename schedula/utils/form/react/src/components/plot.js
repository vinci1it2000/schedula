import React, {Suspense} from "react";
import cloneDeep from 'lodash/cloneDeep'
import Plotly from "plotly.js-cartesian-dist-min";
import createPlotlyComponent from "react-plotly.js/factory";
const Plot = createPlotlyComponent(Plotly);

export default function _plot(props) {
    let {context, children, ...kw} = props
    return <Suspense>
        <Plot {...Object.assign(cloneDeep(context.props.formData || {}), kw)}/>
    </Suspense>
}
