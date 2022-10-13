import Plot from 'react-plotly.js';


export default function _plot(props) {
    let {context, children, ...kw} = props
    return <Plot {...Object.assign({}, context.props.formData, kw)}/>

}
