import {Row as BaseRow} from 'antd';

const Row = ({children, render, ...props}) => (
    <BaseRow style={{margin: 0}} {...props}>
        {children}
    </BaseRow>);
export default Row;