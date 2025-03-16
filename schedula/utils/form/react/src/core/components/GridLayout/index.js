import {Component, useMemo} from "react";
import {Responsive, WidthProvider} from "react-grid-layout";
import './GridLayout.css'

const ResponsiveGridLayout = WidthProvider(Responsive);

class Layout extends Component {
    static defaultProps = {
        className: "layout",
        rowHeight: null,
        onLayoutChange: function () {
        },
        compactType: null,
        cols: {lg: 12, md: 12, sm: 12, xs: 12, xxs: 12},
    };

    state = {
        currentBreakpoint: "lg",
        mounted: false,
    };

    componentDidMount() {
        this.setState({mounted: true});
    }

    onLayoutChange = (layout, layouts) => {
        this.props.onLayoutChange(layout, layouts);
        this.setState({layouts});
    };

    generateDOM() {
        return this.props.children.map((child, index) => (
            <div key={`${index}`}>
                <div className="react-grid-item-border top"/>
                <div className="react-grid-item-border left"/>
                <div className="react-grid-item-border right"/>
                <div className="react-grid-item-border bottom"/>
                <div className="child-container">
                    {child}
                </div>
            </div>
        ))
    }

    render() {
        return <ResponsiveGridLayout
            key={'gridLayout'}
            measureBeforeMount={false}
            useCSSTransforms={this.state.mounted}
            preventCollision={!this.props.compactType}
            {...this.props}
            onLayoutChange={this.onLayoutChange}>
            {this.generateDOM()}
        </ResponsiveGridLayout>
    }
}


const GridLayout = (
    {
        children,
        render,
        layouts: _layouts,
        cols = {lg: 12, md: 12, sm: 12, xs: 12, xxs: 12},
        ...props
    }
) => {
    const layouts = useMemo(() => {
        let layouts = _layouts
        if (!_layouts) {
            layouts = {}
            const w = 2, h = 4;
            Object.keys(cols).forEach((key) => {
                const n = cols[key];
                layouts[key] = children.map((element, i) => ({
                    i: `${i}`,
                    x: (i * w) % n,
                    y: Math.floor(i * w / n) * h,
                    w,
                    h,
                    minW: 0,
                    maxW: Infinity,
                    minH: 0,
                    maxH: Infinity,
                    // If true, equal to `isDraggable: false, isResizable: false`.
                    static: false,
                    // If false, will not be draggable. Overrides `static`.
                    isDraggable: true,
                    // If false, will not be resizable. Overrides `static`.
                    isResizable: true,
                    // By default, a handle is only shown on the bottom-right (southeast) corner.
                    // As of RGL >= 1.4.0, resizing on any corner works just fine!
                    resizeHandles: ['se'], // ['s', 'w' , 'e' , 'n' , 'sw' , 'nw' , 'se' , 'ne']
                    // If true and draggable, item will be moved only within grid.
                    isBounded: false
                }))
            })
        }
        return layouts
    }, [_layouts]);
    return <div key={'grid'} className={'grid-layout-container'}
                style={{height: '100%', width: '100%', overflow: 'auto'}}>
        <Layout draggableHandle={'.react-grid-item-border'}
                layouts={layouts} {...props}>
            {children}
        </Layout>
    </div>
};
export default GridLayout;