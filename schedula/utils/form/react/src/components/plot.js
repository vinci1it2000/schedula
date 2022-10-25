import Plot from 'react-plotly.js';
import cloneDeep from 'lodash/cloneDeep'

export default function _plot(props) {
    let {context, children, ...kw} = props
    return <Plot {...Object.assign(cloneDeep(context.props.formData), kw)}/>

}
