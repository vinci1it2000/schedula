import {Card} from 'antd';

const {Grid: BaseGrid} = Card,
    Grid = ({children, render, ...props}) => (
        <BaseGrid {...props}>
            {children}
        </BaseGrid>);
export default Grid;