import React, {Suspense} from "react";
import cloneDeep from 'lodash/cloneDeep'

const Plot = React.lazy(() => import('react-plotly.js'));

export default function _plot(props) {
    let {context, children, ...kw} = props
    return <Suspense>
        <Plot {...Object.assign(cloneDeep(context.props.formData || {}), kw)}/>
    </Suspense>
}
