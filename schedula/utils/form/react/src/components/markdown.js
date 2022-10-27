import React from 'react';

const MuiMarkdown = React.lazy(() => import('mui-markdown'));

function format2(string, args = [], kwargs = {}) {
    let i = -1;
    return string.replace(/{(\d+)}/g, function (match, number) {
        return typeof args[number] != 'undefined' ? args[number] : match;
    }).replace(/{(\w[^}]*)}/g, function (match, key) {
        return typeof kwargs[key] != 'undefined' ? kwargs[key] : match;
    }).replace(/{(\s*)}/g, function (match) {
        i++;
        return typeof args[i] != 'undefined' ? args[i] : match;
    });
};
export default function _markdown(props) {
    let args = [], kwargs = {}, data = props.context.props.formData || {};
    if (typeof data !== 'object') {
        args = [data]
    } else if (Array.isArray(data)) {
        args = data
    } else {
        kwargs = data
    }

    let md = format2(props.children.join('\n'), args, kwargs);
    return (<MuiMarkdown>
        {md}
    </MuiMarkdown>);
}