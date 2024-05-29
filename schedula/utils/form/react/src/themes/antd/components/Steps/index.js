import {Steps as BaseSteps} from 'antd';
import {useState} from 'react';

const Steps = ({children, render, items, ...props}) => {
    const [current, setCurrent] = useState(0);
    const onChange = (value) => {
        setCurrent(value);
    };
    const _items = items.map((item, index) => (
        {key: index, ...item, ...(index === current ? {status: 'process'} : {})}
    ))
    return <div style={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        overflowY: "hidden"
    }}>
        <BaseSteps
            current={current}
            onChange={onChange}
            items={_items}
            {...props}
        />
        <div style={{
            overflowY: 'hidden',
            flexGrow: 1,
            paddingTop: 6,
            paddingBottom: 6
        }}>{children[current]}</div>
    </div>
};
export default Steps;