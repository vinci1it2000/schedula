import {Splitter as BaseSplitter} from 'antd';

const Splitter = ({children, render, ...props}) => (
    <BaseSplitter autoplay={true} {...props}>
        {children}
    </BaseSplitter>
);
export default Splitter;